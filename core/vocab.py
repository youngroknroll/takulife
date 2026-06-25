"""
core/vocab.py — Single source of domain vocabulary for TakuLog.

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
    ("online", "온라인"),
)

REGION_LABELS: dict[str, str] = dict(REGION)

# ---------------------------------------------------------------------------
# Archive / user-event status vocabulary
# These are the statuses a user assigns to an event they are tracking.
# The slug IS the canonical CSS class name (G10 unification).
# slug → display label
# ---------------------------------------------------------------------------
# "interested" is no longer an archive status — it lives in EventInterest.
# The label is kept as a module constant for use in interest widgets and lists.
INTEREST_LABEL = "관심"

ARCHIVE_STATUS: tuple[tuple[str, str], ...] = (
    ("planned", "방문 예정"),
    ("visited", "방문 완료"),
    ("missed", "놓침"),
)

ARCHIVE_STATUS_LABELS: dict[str, str] = dict(ARCHIVE_STATUS)

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
