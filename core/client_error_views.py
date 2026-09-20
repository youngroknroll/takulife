"""POST /api/client-errors/ — 프론트 오류 보고 수집(트랙 36 S5).

인증 없이 브라우저에서 직접 호출하는, 이 저장소 첫 공개 쓰기 엔드포인트다.
어떤 입력이 와도 절대 500·에러 상세를 돌려주지 않는다(정보 비노출) — 허용된
형태가 아니면 그냥 204로 조용히 넘어간다.
"""
import json
import logging
import re
from urllib.parse import urlparse, urlsplit

from django.core.exceptions import RequestDataTooBig
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.error_groups import compute_fingerprint, frontend_new_group_allowed, record_error

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 4096
_ALLOWED_KEYS = {"message", "name", "script", "line", "col"}
_REQUIRED_KEYS = {"message", "script", "line"}
_STR_KEYS = {"message", "name", "script"}
_INT_KEYS = {"line", "col"}
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def normalize_path(path):
    """숫자·UUID 세그먼트를 ":id"로 접어 같은 모양의 경로가 같은 위치로
    묶이게 한다(쿼리·프래그먼트는 항상 지운다)."""
    clean_path = urlsplit(path).path
    segments = [
        ":id" if segment.isdigit() or _UUID_RE.match(segment) else segment
        for segment in clean_path.split("/")
    ]
    return "/".join(segments)


def _is_same_origin(request):
    """Origin 헤더가 있으면 그 출처만, 없으면 Referer 출처만 본다. 이 검사는
    정상 브라우저 요청의 잡음만 걸러낼 뿐 진짜 방어는 아니다 — curl 등은
    두 헤더 모두 얼마든지 위조할 수 있다(SRR F7)."""
    candidate = request.META.get("HTTP_ORIGIN") or request.META.get("HTTP_REFERER")
    if not candidate:
        return False
    return urlparse(candidate).netloc == request.get_host()


def _parse_json_body(request):
    try:
        body = request.body
    except RequestDataTooBig:
        # DATA_UPLOAD_MAX_MEMORY_SIZE 초과는 request.body 접근 자체에서
        # 터진다 — "항상 204" 계약을 지키려면 여기서도 조용히 넘어가야 한다.
        return None
    if len(body) > MAX_BODY_BYTES:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _is_valid_int(value):
    # bool은 int의 서브클래스라 isinstance(True, int)가 True다 — line·col에
    # True/False가 들어오는 것을 막으려면 타입을 정확히 가려야 한다.
    return type(value) is int


def _is_valid_payload(data):
    if not isinstance(data, dict) or not set(data.keys()) <= _ALLOWED_KEYS:
        return False
    if not _REQUIRED_KEYS <= set(data.keys()):
        return False
    if any(key in data and not isinstance(data[key], str) for key in _STR_KEYS):
        return False
    if any(key in data and not _is_valid_int(data[key]) for key in _INT_KEYS):
        return False
    if not data["script"].strip():
        return False
    return True


class GlobalClientErrorThrottle(ScopedRateThrottle):
    """이 API는 미인증이라 기본 스로틀이 요청 IP를 식별자로 쓰는데, 저장소에
    프록시 개수 설정이 없어 X-Forwarded-For를 그대로 믿는다(러너 스로틀과
    같은 문제). 헤더 우회를 막기 위해 IP 대신 고정 식별자 하나로 묶는다."""

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": "global"}


@extend_schema(exclude=True)
class ClientErrorReportView(APIView):
    # 이 저장소 첫 공개(비인증) 쓰기 엔드포인트 — 스로틀·페이로드 검증으로
    # 남용을 막을 뿐 로그인 여부는 아예 확인하지 않는다.
    authentication_classes = []
    permission_classes = []
    # DRF 기본 파서를 쓰지 않는다 — request.data가 잘못된 JSON에서 곧장
    # 400을 내버려 "정보 비노출" 계약(항상 204)을 지킬 수 없기 때문이다.
    parser_classes = []
    throttle_classes = [GlobalClientErrorThrottle]
    throttle_scope = "client_error_report"

    def handle_exception(self, exc):
        if isinstance(exc, Throttled):
            # 스로틀 초과도 정보 비노출 계약을 지킨다 — 429 대신 조용히 204.
            return Response(status=204)
        # 이 엔드포인트는 "항상 204"가 계약이다 — 다른 예외도 500 대신
        # 조용히 204로 넘기고, 원인은 서버 로그에만 남긴다(EHL 정책).
        logger.exception("client error report failed")
        return Response(status=204)

    def post(self, request):
        if not _is_same_origin(request):
            return Response(status=204)

        data = _parse_json_body(request)
        if not _is_valid_payload(data):
            return Response(status=204)

        name = data.get("name") or "unknown"
        error_type = "js:" + str(name)[:60]
        location = f"{normalize_path(data.get('script') or '')}:{data.get('line')}"
        fingerprint = compute_fingerprint("frontend", error_type, location)

        if frontend_new_group_allowed(fingerprint):
            record_error(
                source="frontend",
                error_type=error_type,
                location=location,
                message=data.get("message", ""),
            )
        return Response(status=204)
