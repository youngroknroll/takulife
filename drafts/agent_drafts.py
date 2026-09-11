"""러너가 제출한 키워드 탐색 이벤트 페이로드를 서버가 재검사하는 자리다.
서버는 여기서 인스타·X를 절대 가져오지 않는다 — 이 계약은 KW-07이 나중에
테스트로 고정한다."""
import unicodedata
from datetime import date
from urllib.parse import urlsplit

from django.db import transaction

from core.vocab import is_valid_category, is_valid_region
from drafts.discovery import SNS_HOSTNAMES
from drafts.discovery_runs import locked_run_with_valid_lease, renew_lease
from drafts.fetching import fetch_html
from drafts.models import EventDraft
from drafts.robots import RobotsChecker
from drafts.services import create_draft_from_fields
from drafts.url_safety import validate_fetch_url

_REQUIRED_KEYS = (
    "source_url",
    "raw_title",
    "raw_text",
    "fields",
    "confidence",
    "note",
    "platform",
    "judgment",
    "official_basis",
    "source_name",
)

_MAX_SOURCE_URL_LENGTH = 200

# note에 인용하는 원값이 메모를 부풀리지 않도록 자르는 상한. 계획서가 캡션
# 인용 상한으로 쓴 80자를 그대로 따른다(§D evidence≤80자 원문 인용).
_MAX_QUOTED_VALUE_LENGTH = 80

_CATEGORY_MISMATCH_NOTE = "카테고리 값 불일치(원값 {value})"
_REGION_MISMATCH_NOTE = "지역 값 불일치(원값 {value})"
_CONFIDENCE_MISMATCH_NOTE = "confidence 값 불일치(원값 {value})"
_DATE_REVERSED_NOTE = "기간 역전(시작 {start}, 종료 {end})"

# 오작동하는 러너가 한 실행에서 이벤트를 무한정 밀어넣는 것을 막는 심층 방어.
MAX_EVENTS_PER_RUN = 20

# 판단값 → 메모 앞머리 표시 문구. official이거나 목록 밖 값이면 접두를 붙이지 않는다.
_JUDGMENT_NOTE_PREFIXES = {
    "unofficial": "탐색 판단: 비공식",
    "unclear": "탐색 판단: 불명",
}

# 계획서 페이로드 계약의 note 상한(prompt_plan.md:292 note≤1000)을 그대로 따른다.
_MAX_NOTE_LENGTH = 1000


class EventLimitExceededError(Exception):
    pass


def _strip_control_chars(*, value):
    return "".join(char for char in value if unicodedata.category(char) != "Cc")


def _quote_original_value(value):
    return _strip_control_chars(value=str(value))[:_MAX_QUOTED_VALUE_LENGTH]


def _check_category(*, fields, note_additions):
    category = fields.get("category", "")
    if not is_valid_category(category):
        note_additions.append(
            _CATEGORY_MISMATCH_NOTE.format(value=_quote_original_value(category))
        )
        fields["category"] = ""


def _check_region(*, fields, note_additions):
    region = fields.get("region", "")
    if not is_valid_region(region):
        note_additions.append(
            _REGION_MISMATCH_NOTE.format(value=_quote_original_value(region))
        )
        fields["region"] = ""


def _check_confidence(*, cleaned, note_additions):
    confidence = cleaned.get("confidence")
    # bool은 숫자로 취급하지 않는다 — isinstance(True, int)가 참이라 그냥
    # 두면 True가 신뢰도 1.0으로 통과해 버린다.
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not (0 <= confidence <= 1)
    ):
        note_additions.append(
            _CONFIDENCE_MISMATCH_NOTE.format(value=_quote_original_value(confidence))
        )
        cleaned["confidence"] = None


def _check_date_range(*, fields, note_additions):
    start_value = fields.get("start_date")
    end_value = fields.get("end_date")
    if not start_value or not end_value:
        return
    try:
        start_date = date.fromisoformat(start_value)
        end_date = date.fromisoformat(end_value)
    except (TypeError, ValueError):
        return
    if start_date > end_date:
        note_additions.append(
            _DATE_REVERSED_NOTE.format(
                start=_quote_original_value(start_value),
                end=_quote_original_value(end_value),
            )
        )
        fields["start_date"] = None
        fields["end_date"] = None


def _build_intake_note(*, cleaned):
    prefix_label = _JUDGMENT_NOTE_PREFIXES.get(cleaned.get("judgment"))
    note = cleaned["note"]
    if prefix_label is None:
        return note

    official_basis = _strip_control_chars(value=str(cleaned.get("official_basis", "")))
    prefix = f"{prefix_label} — {official_basis}"
    combined = f"{prefix}\n{note}" if note else prefix
    return combined[:_MAX_NOTE_LENGTH]


def parse_agent_draft_payload(*, payload):
    valid = all(key in payload for key in _REQUIRED_KEYS)

    source_url = payload.get("source_url", "")
    if (
        not isinstance(source_url, str)
        or not source_url.startswith(("http://", "https://"))
        or len(source_url) > _MAX_SOURCE_URL_LENGTH
    ):
        valid = False

    cleaned = dict(payload)
    if isinstance(cleaned.get("fields"), dict):
        cleaned["fields"] = dict(cleaned["fields"])

    if valid:
        note_additions = []
        fields = cleaned["fields"]
        _check_category(fields=fields, note_additions=note_additions)
        _check_region(fields=fields, note_additions=note_additions)
        _check_confidence(cleaned=cleaned, note_additions=note_additions)
        _check_date_range(fields=fields, note_additions=note_additions)
        if note_additions:
            cleaned["note"] = " ".join([cleaned["note"], *note_additions]).strip()

    return cleaned, (None if valid else "schema")


def submit_agent_draft(*, run_id, lease_token, payload):
    """앞으로 judgment 접두·메모 조립을 순서대로 붙여 나갈 자리다. 지금은
    임대 확인(잠금 A) → 잠금 밖에서 서버 재확인(네트워크, SNS 호스트는 건너뜀)
    → 임대 재확인·중복·상한 확인·생성(잠금 B) 순서로 처리한다. 재확인이
    네트워크를 타 오래 걸릴 수 있어 그 동안 실행 행 잠금을 쥐지 않는다."""
    cleaned, stage = parse_agent_draft_payload(payload=payload)
    fields = cleaned["fields"]

    with transaction.atomic():
        locked_run_with_valid_lease(run_id=run_id, lease_token=lease_token)

    hostname = urlsplit(cleaned["source_url"]).hostname
    if hostname not in SNS_HOSTNAMES:
        validate_fetch_url(cleaned["source_url"])
        RobotsChecker().check(cleaned["source_url"])
        fetch_html(cleaned["source_url"])

    with transaction.atomic():
        run = locked_run_with_valid_lease(run_id=run_id, lease_token=lease_token)
        renew_lease(run=run)

        existing = EventDraft.objects.filter(source_url=cleaned["source_url"]).first()
        if existing is not None:
            return existing, False

        if run.events.count() >= MAX_EVENTS_PER_RUN:
            raise EventLimitExceededError

        draft = create_draft_from_fields(
            source_url=cleaned["source_url"],
            source_name=cleaned["source_name"],
            title=fields.get("title", ""),
            category=fields.get("category", ""),
            work_title=fields.get("work_title", ""),
            location_name=fields.get("location_name", ""),
            region=fields.get("region", ""),
            summary=fields.get("summary", ""),
            raw_title=cleaned["raw_title"],
            raw_text=cleaned["raw_text"],
            start_date=fields.get("start_date"),
            end_date=fields.get("end_date"),
            confidence=cleaned["confidence"],
            extraction_method=EventDraft.ExtractionMethod.LLM,
            intake_note=_build_intake_note(cleaned=cleaned),
            discovery_run=run,
        )
        return draft, True
