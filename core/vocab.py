"""
core/vocab.py — Single source of domain vocabulary for takulife.

This module defines canonical slug→label mappings for categories, regions,
archive statuses, and event statuses. All templates, context processors, and
future filter validators must reference these constants rather than maintaining
their own local copies.

Design decisions (per prompt_plan.md §3.4, confirmed 2026-06-24):
- Slug keys (left side) are what the API stores and filters on.
- Korean labels (right side) are what the UI displays.
- The canonical CSS class for archive/user-event status IS the slug itself
  (interested / planned / visited / missed), replacing the old wish/plan/done/miss
  class names used in early mock templates.
- Exposed as plain tuples/dicts (no magic, no metaclasses, immutable-friendly).
"""

# ---------------------------------------------------------------------------
# Event category vocabulary
# slug → display label
# ---------------------------------------------------------------------------
CATEGORY: tuple[tuple[str, str], ...] = (
    ("popup_store", "팝업스토어"),
    ("collaboration_cafe", "콜라보 카페"),
    ("theater_bonus", "극장 특전"),
    ("goods_reservation", "굿즈 예약"),
    ("exhibition", "전시"),
    ("fan_meeting", "팬미팅"),
)

# Convenience dict for O(1) label lookup.
CATEGORY_LABELS: dict[str, str] = dict(CATEGORY)

# ---------------------------------------------------------------------------
# Region vocabulary
# slug → display label
# ---------------------------------------------------------------------------
REGION: tuple[tuple[str, str], ...] = (
    ("seoul", "서울"),
    ("gyeonggi", "경기"),
    ("incheon", "인천"),
    ("busan", "부산"),
    # 대구·대전·광주는 2026-07-23에 추가됐다. 실데이터가 이미 이 세 도시를
    # 쓰고 있었는데 어휘에 없어 지역 필터 어디에도 걸리지 않았다 — 어휘 가드를
    # 걸기 전에 먼저 메워야 했던 구멍이다.
    ("daegu", "대구"),
    ("daejeon", "대전"),
    ("gwangju", "광주"),
    ("online", "온라인"),
)

REGION_LABELS: dict[str, str] = dict(REGION)

# ---------------------------------------------------------------------------
# Archive / user-event status vocabulary
# These are the statuses a user assigns to an event they are tracking.
# The slug IS the canonical CSS class name (G10 unification).
# slug → display label
# ---------------------------------------------------------------------------
ARCHIVE_STATUS: tuple[tuple[str, str], ...] = (
    ("planned", "방문 예정"),
    ("visited", "방문 완료"),
    ("missed", "놓침"),
)

ARCHIVE_STATUS_LABELS: dict[str, str] = dict(ARCHIVE_STATUS)


# ---------------------------------------------------------------------------
# Collection item type vocabulary (D4)
# Free-input on the model (no DB choices constraint) — this is UI-side
# guidance for CollectionItem.item_type. slug → display label
# ---------------------------------------------------------------------------
COLLECTION_ITEM_TYPE: tuple[tuple[str, str], ...] = (
    ("acrylic_stand", "아크릴 스탠드"),
    ("keyring", "키링"),
    ("badge", "뱃지"),
    ("photocard", "포토카드"),
    ("plush", "인형"),
    ("stationery", "문구"),
    ("etc", "기타"),
)

COLLECTION_ITEM_TYPE_LABELS: dict[str, str] = dict(COLLECTION_ITEM_TYPE)


def archive_status_label(slug: str) -> str:
    return ARCHIVE_STATUS_LABELS.get(slug, slug)


# ---------------------------------------------------------------------------
# Archive status list sort vocabulary (slug matches
# archive.queries.ARCHIVE_STATUS_SORT_ORDERING). Empty slug "" is the default
# (등록일 최근 수정순 / -updated_at). slug → display label
# ---------------------------------------------------------------------------
ARCHIVE_STATUS_SORT: tuple[tuple[str, str], ...] = (
    ("", "최근 수정순"),
    ("created_at", "등록순"),
)

ARCHIVE_STATUS_SORT_LABELS: dict[str, str] = dict(ARCHIVE_STATUS_SORT)

# ---------------------------------------------------------------------------
# Event status vocabulary (independent axis from archive status)
# Describes the publication/temporal state of an Event object.
# slug → display label
# ---------------------------------------------------------------------------
EVENT_STATUS: tuple[tuple[str, str], ...] = (
    ("upcoming", "예정"),
    ("ongoing", "진행 중"),
    ("closing_soon", "종료 임박"),
    ("ended", "종료"),
)

EVENT_STATUS_LABELS: dict[str, str] = dict(EVENT_STATUS)

# ---------------------------------------------------------------------------
# Public listing sort vocabulary (event_list ordering).
# Empty slug "" is the default ordering. slug → display label
# ---------------------------------------------------------------------------
EVENT_SORT: tuple[tuple[str, str], ...] = (
    ("", "기본순"),
    ("closing_soon", "종료 임박순"),
    ("start_asc", "시작일 빠른순"),
    ("newest", "최신 등록순"),
)

EVENT_SORT_LABELS: dict[str, str] = dict(EVENT_SORT)


# ---------------------------------------------------------------------------
# Vocabulary membership checks (2026-07-23).
#
# Event.category / Event.region are plain CharFields with no `choices`, so
# nothing at the model or DB layer rejects a value outside these tuples. The
# LLM extraction path already revalidates against the same vocabulary
# (drafts/llm_extraction.py) and the public API is read-only, but the staff
# write paths relied on the template <select> alone — a hand-made POST went
# straight through, which is how free text like "카페/팝업" reached the dev DB
# and silently disabled the category colour system.
#
# These return a bool rather than raising: each caller owns the domain error
# its own layer reports (events.services raises PublishEvent*Error, which the
# staff console maps to a field error; drafts.services raises DraftVocabError).
#
# `choices=` on the model was considered and rejected: this project has no
# ModelForms for events (the staff console builds form_values by hand) and
# CATEGORY_LABELS already covers display, so it would buy nothing while adding
# an AlterField migration to every future vocabulary edit — and this
# vocabulary demonstrably still grows (see the 2026-07-23 REGION additions).
# ---------------------------------------------------------------------------
def is_valid_category(value: str) -> bool:
    """True when `value` is a known category slug or "" (미분류).

    Blank is deliberately valid: category is optional on Event, and rejecting
    it would make an uncategorised event impossible to register.
    """
    return value == "" or value in CATEGORY_LABELS


def is_valid_region(value: str) -> bool:
    """True when `value` is a known region slug or "" (지역 미상).

    Blank is deliberately valid — see is_valid_category.
    """
    return value == "" or value in REGION_LABELS
