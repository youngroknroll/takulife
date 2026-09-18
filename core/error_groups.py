"""core/error_groups.py — 오류 묶음 기록에 앞서 메시지를 정제한다.

원본 로그를 그대로 남기지 않는다. 개행·제어문자를 지우고, 설정에 박힌
시크릿 값이 섞였으면 메시지 전체를 비우고, 이메일을 가리고, URL 쿼리를
잘라 개인정보·인증값이 저장 행에 남지 않게 한다.
"""
import hashlib
import logging
import re

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
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


def compute_fingerprint(source, error_type, location):
    """지문 계산을 공개해 호출자가 record_error 전에 같은 묶음인지 미리
    확인할 수 있게 한다(예: 새 묶음 상한을 판단하는 API 뷰)."""
    return hashlib.sha256(f"{source}|{error_type}|{location}".encode("utf-8")).hexdigest()


def sanitize_message(text):
    """원본 메시지를 저장 가능한 형태로 정제해 돌려준다."""
    cleaned = _EXTRA_SPACES_RE.sub(" ", _CONTROL_CHARS_RE.sub(" ", text)).strip()

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
    """
    error_type_sample = ""
    try:
        error_type_sample = error_type[:100]
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
    updated = ErrorGroup.objects.filter(fingerprint=fingerprint).update(
        count=F("count") + 1, last_seen=now, message_sample=sample
    )
    if updated:
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
        ErrorGroup.objects.filter(fingerprint=fingerprint).update(
            count=F("count") + 1, last_seen=now, message_sample=sample
        )
        return

    _trim_source(ErrorGroup, source=source)


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
