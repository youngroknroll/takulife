"""번역 러너용 API의 얇은 어댑터다. 인증·직렬화·상태코드만 다루고
판정·저장은 events.translation_queue에 위임한다.
"""
import re

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from core.errors import error_response
from core.ip import get_client_ip
from core.runner_auth import RunnerAPIView

from .content_translation import SubmissionRejected
from .translation_queue import pending_events, submit_translation

_REJECTION_STATUS = {
    "schema": status.HTTP_400_BAD_REQUEST,
    "nul": status.HTTP_400_BAD_REQUEST,
    "not_found": status.HTTP_404_NOT_FOUND,
    "manual_locked": status.HTTP_409_CONFLICT,
    "stale_source": status.HTTP_409_CONFLICT,
}

# 서버가 만드는 sha256 hex 형식(64자 소문자 16진수)만 허용한다.
_SOURCE_HASH_RE = re.compile(r"[0-9a-f]{64}")


class _TranslationRunnerView(RunnerAPIView):
    throttle_scope = "translation_runner"


class TranslationPendingView(_TranslationRunnerView):
    # 비밀 토큰 기반 기계 간 러너 경계라 공개 API 문서에서 제외한다.
    @extend_schema(exclude=True)
    def post(self, request):
        return Response({"events": pending_events()})


class TranslationSubmitView(_TranslationRunnerView):
    # 비밀 토큰 기반 기계 간 러너 경계라 공개 API 문서에서 제외한다.
    @extend_schema(exclude=True)
    def post(self, request):
        data = request.data
        event_id = data.get("event_id") if isinstance(data, dict) else None
        source_hash = data.get("source_hash") if isinstance(data, dict) else None

        if (
            not isinstance(data, dict)
            or not isinstance(event_id, int)
            or isinstance(event_id, bool)
            or not isinstance(source_hash, str)
            # 형식이 틀린 해시를 거부 로그에 그대로 찍으면 개행 등으로 로그 줄이 위조될 수 있다.
            or not _SOURCE_HASH_RE.fullmatch(source_hash)
        ):
            return error_response("invalid_payload", status.HTTP_400_BAD_REQUEST)

        try:
            outcome = submit_translation(
                event_id=event_id,
                source_hash=source_hash,
                translations=data.get("translations"),
                client_ip=get_client_ip(request),
            )
        except SubmissionRejected as exc:
            return error_response(exc.code, _REJECTION_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST))

        return Response(
            {"status": outcome.status, "saved": outcome.saved, "quarantined": outcome.quarantined}
        )
