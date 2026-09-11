"""러너가 제출한 키워드 탐색 이벤트 페이로드를 서버가 재검사하는 자리다.
서버는 여기서 인스타·X를 절대 가져오지 않는다 — 이 계약은 KW-07이 나중에
테스트로 고정한다."""
import unicodedata

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


def _strip_control_chars(*, value):
    return "".join(char for char in value if unicodedata.category(char) != "Cc")


def _quote_original_value(value):
    return _strip_control_chars(value=value)[:_MAX_QUOTED_VALUE_LENGTH]


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
        category = fields.get("category", "")
        if not is_valid_category(category):
            note_additions.append(
                _CATEGORY_MISMATCH_NOTE.format(value=_quote_original_value(category))
            )
            fields["category"] = ""
        region = fields.get("region", "")
        if not is_valid_region(region):
            note_additions.append(
                _REGION_MISMATCH_NOTE.format(value=_quote_original_value(region))
            )
            fields["region"] = ""
        if note_additions:
            cleaned["note"] = " ".join([cleaned["note"], *note_additions]).strip()

    return cleaned, (None if valid else "schema")
