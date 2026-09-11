"""러너가 제출한 키워드 탐색 이벤트 페이로드를 서버가 재검사하는 자리다.
서버는 여기서 인스타·X를 절대 가져오지 않는다 — 이 계약은 KW-07이 나중에
테스트로 고정한다."""
import unicodedata
from datetime import date

from core.vocab import is_valid_category, is_valid_region

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
