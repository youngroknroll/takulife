"""core/error_groups.py — 오류 묶음 기록에 앞서 메시지를 정제한다.

원본 로그를 그대로 남기지 않는다. 개행·제어문자를 지우고, 설정에 박힌
시크릿 값이 섞였으면 메시지 전체를 비우고, 이메일을 가리고, URL 쿼리를
잘라 개인정보·인증값이 저장 행에 남지 않게 한다.
"""
import hashlib
from datetime import timedelta
import logging
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

_CONTROL_CHARS_RE = re.compile(r"[\r\n\t\x00-\x1f\x7f]+")
_EXTRA_SPACES_RE = re.compile(r" {2,}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"(https?://[^\s?#]+)(?:\?[^\s#]*)?(?:#\S*)?")

MESSAGE_SAMPLE_MAX_LENGTH = 500
# 출처별 상한 — 이 값이 없으면 익명 프론트 오류 보고가 백엔드 묶음을
# 무한정 밀어낼 수 있다(합 500행 근사, 동시 생성 시 ±1~2행 허용).
SOURCE_GROUP_LIMIT = 250

# 대시보드 패널이 그대로 쓰는 표시용 한국어 라벨(system_error_summary 전용).
_SOURCE_LABELS = {"backend": "백엔드", "frontend": "프론트"}


def _configured_secrets():
    """저장 전 대조할 설정값 목록. 비어 있는 값은 대조 대상에서 뺀다 —
    빈 문자열은 모든 문자열에 포함되어 모든 메시지를 지워버린다."""
    database_password = settings.DATABASES.get("default", {}).get("PASSWORD", "")
    candidates = [
        settings.SECRET_KEY,
        settings.ANTHROPIC_API_KEY,
        settings.DRAFT_DISCOVERY_RUNNER_TOKEN,
        database_password,
    ]
    return [value for value in candidates if value]


def _contains_secret(text):
    return any(secret in text for secret in _configured_secrets())


def _mask_emails(text):
    return _EMAIL_RE.sub("[email]", text)


def _strip_url_queries(text):
    return _URL_RE.sub(lambda match: match.group(1), text)


def _strip_control(text):
    """개행·탭·제어문자를 지우고 중복 공백을 접어 로그·DB에 한 줄만
    남게 한다(sanitize_message와 같은 정제를 error_type·location에도
    적용하기 위한 공용 조각)."""
    return _EXTRA_SPACES_RE.sub(" ", _CONTROL_CHARS_RE.sub(" ", text)).strip()


def _normalize_key(error_type, location):
    """지문 계산과 저장이 항상 같은 값을 보도록 error_type·location을
    한 곳에서 정규화한다(제어문자 제거 + 길이 절단)."""
    return _strip_control(error_type)[:100], _strip_control(location)[:255]


def compute_fingerprint(source, error_type, location):
    """지문 계산을 공개해 호출자가 record_error 전에 같은 묶음인지 미리
    확인할 수 있게 한다(예: 새 묶음 상한을 판단하는 API 뷰). 함수 스스로
    정규화하므로 호출자가 원본 값을 넘겨도 record_error가 저장하는
    지문과 항상 같다. 구분자는 "\x1f"(제어문자) — 정규화 후 값에는
    제어문자가 남지 않으므로 "a|b","c"와 "a","b|c"처럼 필드 경계가
    문자로 뒤섞이는 일이 없다."""
    normalized_error_type, normalized_location = _normalize_key(error_type, location)
    key = f"{source}\x1f{normalized_error_type}\x1f{normalized_location}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def sanitize_message(text):
    """원본 메시지를 저장 가능한 형태로 정제해 돌려준다."""
    cleaned = _strip_control(text)

    if _contains_secret(cleaned):
        return ""

    cleaned = _mask_emails(cleaned)
    cleaned = _strip_url_queries(cleaned)
    return cleaned[:MESSAGE_SAMPLE_MAX_LENGTH]


def record_error(*, source, error_type, location, message):
    """지문(source|error_type|location)이 같은 오류를 한 행으로 묶는다.

    절대 예외를 던지지 않는다 — 오류 기록 자체가 실패해도 호출한 요청을
    깨뜨리면 안 된다(core.analytics.record_event와 같은 형태). 저장은
    자체 중첩 atomic()(세이브포인트) 안에서 실행해, 호출자가 이미 깨진
    트랜잭션 안에 있어도(예: 다른 곳에서 IntegrityError를 세이브포인트
    없이 삼킨 경우) 이 함수의 실패가 그 트랜잭션을 더 오염시키지 않는다.
    error_type·location은 진입 즉시 제어문자를 없애 지문·저장·경고
    로그 어디에도 개행이 섞이지 않게 한다.
    """
    error_type_sample = ""
    try:
        error_type, location = _normalize_key(error_type, location)
        error_type_sample = error_type
        fingerprint = compute_fingerprint(source, error_type, location)
        sample = sanitize_message(message)
        now = timezone.now()

        from core.models import ErrorGroup

        with transaction.atomic():
            _upsert_error_group(
                ErrorGroup,
                fingerprint=fingerprint,
                source=source,
                error_type_sample=error_type_sample,
                location=location,
                sample=sample,
                now=now,
            )
    except Exception:  # except-ok: 오류 기록 실패가 호출자의 요청을 깨뜨리면 안 된다
        logger.warning(
            "error-group record failed: source=%s error_type=%s",
            source,
            error_type_sample,
        )


def _upsert_error_group(ErrorGroup, *, fingerprint, source, error_type_sample, location, sample, now):
    """기존 지문이면 count만 늘리고, 새 지문이면 만든다.

    동시에 다른 트랜잭션이 같은 지문을 먼저 만들었으면(경합) create()가
    IntegrityError를 내는데, 이때도 그 행을 잃지 않고 count를 반영해야
    하므로 update로 한 번 더 시도한다(DAR 결정: update → 0행이면 create
    → IntegrityError면 update). create()는 자체 세이브포인트 안에서
    실행해, 실패해도 바깥의 갱신 시도에 영향을 남기지 않는다.
    """
    if _bump(ErrorGroup, fingerprint=fingerprint, now=now, sample=sample):
        return

    try:
        with transaction.atomic():
            created = ErrorGroup.objects.create(
                source=source,
                fingerprint=fingerprint,
                error_type=error_type_sample,
                location=location[:255],
                message_sample=sample,
                first_seen=now,
                last_seen=now,
            )
    except IntegrityError:
        _bump(ErrorGroup, fingerprint=fingerprint, now=now, sample=sample)
        return

    _trim_source(ErrorGroup, source=source)


def _bump(ErrorGroup, *, fingerprint, now, sample):
    """기존 지문 행의 count·last_seen·message_sample만 갱신한다. 갱신된
    행 수(0 또는 1)를 돌려줘 호출자가 "이미 있던 지문인지"를 판단하게
    한다."""
    return ErrorGroup.objects.filter(fingerprint=fingerprint).update(
        count=F("count") + 1, last_seen=now, message_sample=sample
    )


def _trim_source(ErrorGroup, *, source):
    """새 묶음 생성으로 그 출처가 상한을 넘으면 최고령(last_seen) 행부터
    지운다. 방금 만든 행은 last_seen=now라 정렬상 항상 최신이라 최고령이
    될 수 없으므로 별도로 빼지 않는다. update 경로나 IntegrityError
    재시도 경로(기존 행 갱신)에서는 부르지 않는다 — 새 행이 실제로
    생겼을 때만 상한을 넘을 수 있다."""
    excess = ErrorGroup.objects.filter(source=source).count() - SOURCE_GROUP_LIMIT
    if excess <= 0:
        return
    stale_ids = list(
        ErrorGroup.objects.filter(source=source)
        .order_by("last_seen", "id")
        .values_list("id", flat=True)[:excess]
    )
    ErrorGroup.objects.filter(id__in=stale_ids).delete()


def prune_stale_error_groups(*, days, dry_run=False):
    """last_seen이 days일보다 오래된 오류 묶음을 지운다(운영 보존 정리 전용).

    dry_run이면 지우지 않고 대상 건수만 센다.
    """
    from core.models import ErrorGroup

    cutoff = timezone.now() - timedelta(days=days)
    queryset = ErrorGroup.objects.filter(last_seen__lt=cutoff)

    if dry_run:
        return queryset.count()

    deleted, _ = queryset.delete()
    return deleted


def system_error_summary(*, now=None, limit=5):
    """대시보드 "시스템 오류" 패널이 그대로 쓰는 요약을 계산한다.

    쿼리 2회 고정(집계 1회 + 상위 목록 1회) — 묶음이 0건이든 다건이든
    같은 수의 쿼리만 나가도록 aggregate와 슬라이스 조회로 나눈다.
    """
    from core.models import ErrorGroup

    now = now or timezone.now()

    totals = ErrorGroup.objects.aggregate(
        total=Count("id"),
        window_24h=Count("id", filter=Q(last_seen__gte=now - timedelta(hours=24))),
        window_7d=Count("id", filter=Q(last_seen__gte=now - timedelta(days=7))),
        backend=Count("id", filter=Q(source=ErrorGroup.Source.BACKEND)),
        frontend=Count("id", filter=Q(source=ErrorGroup.Source.FRONTEND)),
    )

    top_rows = ErrorGroup.objects.order_by("-last_seen", "-id").values(
        "source", "error_type", "location", "count", "last_seen"
    )[:limit]
    top = [
        {
            "source": row["source"],
            "source_label": _SOURCE_LABELS.get(row["source"], row["source"]),
            "error_type": row["error_type"],
            "location": row["location"],
            "count": row["count"],
            "last_seen": row["last_seen"],
        }
        for row in top_rows
    ]

    return {
        "total": totals["total"],
        "window_24h": totals["window_24h"],
        "window_7d": totals["window_7d"],
        "by_source": {"backend": totals["backend"], "frontend": totals["frontend"]},
        "top": top,
    }
