"""번역 대기 큐 조회와 제출 저장을 맡는 DB 계층이다.
해시·검증 같은 순수 규칙은 전부 content_translation 모듈이 갖고 있다.
"""

from dataclasses import dataclass
import logging

from django.db import transaction

from events import content_translation as rules
from events.models import Event

logger = logging.getLogger(__name__)

PENDING_LIMIT = 20


@dataclass(frozen=True)
class SubmissionOutcome:
    status: str
    saved: list
    quarantined: dict


def _event_fields(event):
    return {name: getattr(event, name) for name in rules.TRANSLATED_FIELDS}


def pending_events(*, limit=PENDING_LIMIT):
    if limit <= 0:
        return []

    results = []
    columns = ("id", "text_translations", *rules.TRANSLATED_FIELDS)
    queryset = Event.objects.published().order_by("id").only(*columns).iterator()
    for event in queryset:
        stored = event.text_translations
        if not isinstance(stored, dict):
            stored = {}
        if stored.get("manual"):
            continue

        fields = _event_fields(event)
        current_hash = rules.source_hash(fields)
        if stored.get("source_hash") == current_hash:
            continue

        results.append({"event_id": event.id, "source_hash": current_hash, "fields": fields})
        if len(results) >= limit:
            break
    return results


def queue_report():
    """게시 이벤트를 훑어 대기·최신·수동·언어별 격리 건수를 센다. 쓰기는
    하지 않는다 — 집계만 하는 읽기 전용 보고다."""
    counts = {
        "published": 0,
        "pending": 0,
        "up_to_date": 0,
        "manual": 0,
        "quarantined_en": 0,
        "quarantined_ja": 0,
        "quarantined_zh-hans": 0,
    }

    columns = ("id", "text_translations", *rules.TRANSLATED_FIELDS)
    queryset = Event.objects.published().only(*columns).iterator()
    for event in queryset:
        counts["published"] += 1

        stored = event.text_translations
        if not isinstance(stored, dict):
            stored = {}

        if stored.get("manual"):
            counts["manual"] += 1
            continue

        current_hash = rules.source_hash(_event_fields(event))
        if stored.get("source_hash") != current_hash:
            counts["pending"] += 1
            continue

        counts["up_to_date"] += 1
        for language in rules.TARGET_LANGUAGES:
            if stored.get(language) is None:
                counts[f"quarantined_{language}"] += 1

    return counts


def _submit_translation_locked(*, event_id, source_hash, translations):
    with transaction.atomic():
        try:
            event = Event.objects.select_for_update().get(
                pk=event_id, publish_status=Event.PublishStatus.PUBLISHED
            )
        except Event.DoesNotExist:
            raise rules.SubmissionRejectedError("not_found")

        stored = event.text_translations
        if not isinstance(stored, dict):
            stored = {}

        if stored.get("manual"):
            raise rules.SubmissionRejectedError("manual_locked")

        fields = _event_fields(event)
        current_hash = rules.source_hash(fields)
        if source_hash != current_hash:
            raise rules.SubmissionRejectedError("stale_source")

        if stored.get("source_hash") == current_hash:
            return SubmissionOutcome(status="already_current", saved=[], quarantined={})

        result = rules.validate_translations(fields, translations)
        saved = [
            language for language in rules.TARGET_LANGUAGES if language not in result.quarantined
        ]

        event.text_translations = {
            "source_hash": current_hash,
            "manual": False,
            **result.languages,
        }
        event.save(update_fields=["text_translations"])

    return SubmissionOutcome(status="saved", saved=saved, quarantined=result.quarantined)


def _log_outcome(*, event_id, outcome, submitted_hash, client_ip):
    level = logging.WARNING if outcome.quarantined else logging.INFO
    logger.log(
        level,
        "translation submission event_id=%s status=%s saved=%s quarantined=%s hash=%s client_ip=%s",
        event_id,
        outcome.status,
        outcome.saved,
        outcome.quarantined,
        submitted_hash[:8],
        client_ip,
    )


def _log_rejection(*, event_id, code, submitted_hash, client_ip):
    logger.warning(
        "translation submission rejected event_id=%s code=%s hash=%s client_ip=%s",
        event_id,
        code,
        submitted_hash[:8],
        client_ip,
    )


def submit_translation(*, event_id, source_hash, translations, client_ip=""):
    try:
        outcome = _submit_translation_locked(
            event_id=event_id, source_hash=source_hash, translations=translations
        )
    except rules.SubmissionRejectedError as exc:
        _log_rejection(
            event_id=event_id, code=exc.code, submitted_hash=source_hash, client_ip=client_ip
        )
        raise

    _log_outcome(
        event_id=event_id, outcome=outcome, submitted_hash=source_hash, client_ip=client_ip
    )
    return outcome
