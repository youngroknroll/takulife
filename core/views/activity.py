"""활동 달력(캘린더) 조회 및 필터 관련 뷰와 헬퍼 모음."""
import logging
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from archive.models import ActivityLogEntry
from archive.queries import (
    GOODS_ACQUIRED_KIND,
    SCHEDULE_KIND,
    VISIT_KIND,
    find_latest_activity_date_for_query,
    list_user_activity_for_month,
    user_status_counts,
)
from core.calendar_grid import month_grid

from ._helpers import _adjacent_month, _parse_calendar_date, _parse_calendar_month

logger = logging.getLogger(__name__)


# 5 user-facing activity groups -> the archive.queries kind constants each
# one covers (dual-calendar service design §7.2/§7.3; mapping given by the
# coordinator's message). "interest" also covers the §7.5 legacy-찜
# fallback, which archive.queries._interest_added_fallback_items already
# reuses ActivityLogEntry.Kind.INTEREST_ADDED for (no separate kind string).
_ACTIVITY_TYPE_GROUPS = {
    "schedule": [SCHEDULE_KIND],
    "interest": [ActivityLogEntry.Kind.INTEREST_ADDED, ActivityLogEntry.Kind.INTEREST_REMOVED],
    "status": [ActivityLogEntry.Kind.STATUS_CHANGED, ActivityLogEntry.Kind.STATUS_REMOVED],
    "visit": [VISIT_KIND, ActivityLogEntry.Kind.VISIT_RECORD_CREATED],
    "goods": [
        GOODS_ACQUIRED_KIND,
        ActivityLogEntry.Kind.COLLECTION_ITEM_CREATED,
        ActivityLogEntry.Kind.COLLECTION_ITEM_ORGANIZED,
    ],
}

_KIND_TO_ACTIVITY_TYPE_GROUP = {
    kind: group for group, kinds in _ACTIVITY_TYPE_GROUPS.items() for kind in kinds
}

# The 4 user-facing groups actually shown in the calendar's legend/cell
# items/selected-date list/counts (activity-calendar editorial plan §4-a
# B2 — "status" stays a real, matchable ?type= group for backward-compat
# bookmarks and _ACTIVITY_TYPE_GROUPS keeps its entry for other possible
# consumers, but it is never rendered or counted anywhere on this page).
_VISIBLE_ACTIVITY_TYPE_GROUPS = ("schedule", "interest", "visit", "goods")


def _visible_activity_group(kind):
    """Map an activity kind to its display group, or None when that kind
    should never appear in the calendar's legend/cell items/selected-date
    list/counts — the single point every one of those four consumers calls
    through, so they can never quietly disagree (BIR Medium: a status-only
    day's aria-label count must match its actually-rendered item count)."""
    group = _KIND_TO_ACTIVITY_TYPE_GROUP.get(kind)
    if group == "status":
        return None
    return group


def _parse_activity_type_filter(request):
    """Return the ?type= values that are one of the 5 valid groups, in
    request order, de-duplicated. An unrecognised value is silently
    ignored (mirrors event_list's existing unrecognised-filter-value
    convention) rather than raising."""
    selected = []
    seen = set()
    for raw_value in request.GET.getlist("type"):
        if raw_value in _ACTIVITY_TYPE_GROUPS and raw_value not in seen:
            seen.add(raw_value)
            selected.append(raw_value)
    return selected


def _activity_extra_query(selected_types):
    """Return the current (already-validated) type= selections as a
    '&type=...&type=...' querystring tail — same leading-'&' convention as
    _calendar_extra_query/_pager.html's extra_query."""
    if not selected_types:
        return ""
    return "&" + urlencode([("type", value) for value in selected_types])


def _format_month_day(value):
    return f"{value.month}월 {value.day}일"


def _activity_filter_url(*, year, month, selected_date, types):
    """Build a full /archive/calendar/ URL preserving the displayed
    month/date and carrying the given ?type= selections (activity-calendar
    editorial plan §8-A B-b — every legend link, toggle or reset, goes
    through this so month/date are never dropped, mirroring the existing
    hidden-input lesson from the date-jump search form)."""
    params = [("month", f"{year:04d}-{month:02d}")]
    if selected_date is not None:
        params.append(("date", selected_date.isoformat()))
    params += [("type", value) for value in types]
    return f"{reverse('archive-calendar-page')}?{urlencode(params)}"


def _activity_kind_filters(*, year, month, selected_date, selected_types, kind_counts):
    """Return the 4 visible groups as clickable legend-filter entries
    (§8-A D2/D3): each is {group, count, is_active, toggle_url}, where
    toggle_url adds the group to the current selection when inactive and
    removes it when active. `count` comes from the caller's filter-independent
    kind_counts (§8-A D1) — never recomputed here from a filtered set."""
    filters = []
    for group in _VISIBLE_ACTIVITY_TYPE_GROUPS:
        is_active = group in selected_types
        if is_active:
            toggled_types = [value for value in selected_types if value != group]
        else:
            toggled_types = selected_types + [group]
        filters.append(
            {
                "group": group,
                "count": kind_counts[group],
                "is_active": is_active,
                "toggle_url": _activity_filter_url(
                    year=year, month=month, selected_date=selected_date, types=toggled_types
                ),
            }
        )
    return filters


def _build_selected_activity_items(items):
    """Reshape the selected date's archive.queries.CalendarActivityItem rows
    into detail-list display dicts: {group, label, url, date_text}.

    `label`/`url` now come straight from CalendarActivityItem (archive/queries.py
    additive extension — each private helper there fills them from the exact
    object it already holds, e.g. Event.title/CollectionItem.name/
    ActivityLogEntry.subject_label for label; event-detail/visit-edit/
    collection-edit reverse() for url, `None` when a SET_NULL target is
    gone). `date_text` is assembled here (day-level from `.date`/`.start`/
    `.end`, plus `.time_text` appended for action-time items — service
    design §9.3's "7월 19일 14:32" example) since that combined format is a
    presentation-only concern.
    """
    display_items = []
    for item in items:
        group = _visible_activity_group(item.kind)
        if group is None:
            continue
        if item.date is not None:
            date_text = _format_month_day(item.date)
            if item.time_text:
                date_text = f"{date_text} {item.time_text}"
        else:
            date_text = f"{_format_month_day(item.start)}~{_format_month_day(item.end)}"
        display_items.append(
            {"group": group, "label": item.label, "url": item.url, "date_text": date_text}
        )
    return display_items


@login_required
def activity_calendar(request):
    """Activity calendar SSR view (dual-calendar plan §단계 5 / PR-D).

    Presentation-only, mirroring event_calendar: month/date parsing reuses
    the exact same _parse_calendar_month/_parse_calendar_date helpers
    (service design §11.1 rules identical), and query/grid-build failures
    degrade the same way (calendar_error="query_failed", never a 500).
    archive.queries.list_user_activity_for_month owns which activity
    belongs to which date — this view only buckets its already-computed
    result by day (grid dot counts/kinds) and reshapes the selected date's
    rows into display dicts.

    Context contract (keys fixed, frontend building templates against this
    in parallel): calendar_error (None|"invalid"|"query_failed"),
    month_label, weeks (7-cell-per-week list of {date, in_month, today,
    selected, count, kinds, items, more_count} — count/kinds/items agree with
    each other and always exclude the "status" group (activity-calendar
    editorial plan §4-a B1/B2: a status-only day counts/shows as empty
    everywhere, not just in the cell — see selected_items/kind_counts below
    too); `items` is the day's first 2 activities as {group, label},
    `more_count` is however many more remain), selected_date,
    selected_items (list of {group, label, url, date_text} — sourced from
    archive.queries.CalendarActivityItem's label/url/time_text fields, see
    _build_selected_activity_items; "status"-group rows are excluded here
    too), prev_month/next_month, extra_query (type= only, month/date
    excluded), selected_types, has_any_items (whole displayed month, under
    the current type filter — see completion report for why this
    simplification was chosen over an always-unfiltered second query;
    derived from items_by_date, so like count/items above it also excludes
    the "status" group — a status-only month renders the empty-state CTA
    the same way a genuinely-empty month does, instead of the previous
    ungated "activity has_any_items but the grid/detail show nothing"
    contradiction), kind_counts (dict of the 4 visible groups -> count, for the displayed
    month, **independent of the current ?type= filter** — activity-calendar
    editorial plan §8-A D1: reuses `items` as-is when no filter narrowed the
    query, otherwise a second unfiltered list_user_activity_for_month call,
    so turning a kind's legend link back on always shows its true count
    rather than the 0 a filtered-source count would leave behind),
    kind_filters (§8-A D2/D3 — the 4 visible groups as clickable legend
    filters: list of {group, count, is_active, toggle_url}; count mirrors
    kind_counts, toggle_url is a full /archive/calendar/ URL that adds the
    group to the current ?type= selection when inactive and removes it when
    active, always preserving month/date), reset_filter_url (a full
    /archive/calendar/ URL with every ?type= cleared, month/date preserved —
    the "전체 보기" affordance for undoing a multi-toggle selection),
    status_counts (archive.queries.user_status_counts(user) verbatim — the
    masthead's whole-history 예정/방문 완료/놓침 totals, independent of the
    displayed month; deliberately a *different* context key from
    kind_counts so the two aggregates never collapse into one binding), q
    (the current ?q= search term, always present even when blank),
    search_no_match (True only when a non-blank q was submitted and matched
    nothing — the search input's value and this flag are what let a
    template render an inline no-match notice without resetting month/date;
    see _search_activity_date_jump below for the redirect-on-match half of
    this contract).

    active_filter_count (the filter-disclosure panel's "N개 선택됨" affordance)
    is deliberately *not* in this context: §8-A D8 removed the disclosure
    panel in favor of the kind_filters legend above, for this view only —
    event_calendar's own active_filter_count context key is untouched.

    "status" stays a real, matchable ?type= group (_ACTIVITY_TYPE_GROUPS is
    unchanged) purely for ?type=status bookmark backward-compatibility
    (§4-a B5) — every rendering/counting consumer above filters it out via
    _visible_activity_group, so such a bookmark now reliably renders a
    genuinely-empty (never crashing, never falsely-nonzero) day instead of
    the previous ungated count.

    Sub-nav active-state note: existing archive/* templates
    (templates/core/archive/*.html) hardcode
    `{% include "core/partials/_archive_nav.html" with active="..." %}"`
    directly in the template, not from a view context key — there is no
    existing "archive_nav_active"-style context convention to mirror, so
    none is added here (confirmed by reading _archive_nav.html and every
    template that includes it).
    """
    today = timezone.localdate()

    year, month, calendar_error = _parse_calendar_month(request.GET.get("month"), today=today)
    selected_date = None
    if calendar_error is None:
        selected_date, calendar_error = _parse_calendar_date(
            request.GET.get("date"), year=year, month=month, today=today
        )

    if calendar_error:
        year, month = today.year, today.month
        selected_date = today

    selected_types = _parse_activity_type_filter(request)
    kinds = None
    if selected_types:
        kinds = [kind for type_group in selected_types for kind in _ACTIVITY_TYPE_GROUPS[type_group]]

    q = request.GET.get("q", "").strip()
    search_no_match = False
    if calendar_error is None and q:
        redirect_response, search_no_match = _search_activity_date_jump(
            request, q=q, selected_types=selected_types
        )
        if redirect_response is not None:
            return redirect_response

    try:
        items = list(
            list_user_activity_for_month(request.user, year=year, month=month, kinds=kinds)
        )
    except Exception:
        logger.exception(
            "Failed to query activity calendar for year=%s month=%s", year, month
        )
        items = []
        if calendar_error is None:
            calendar_error = "query_failed"

    # kind_counts must stay filter-independent (activity-calendar editorial
    # plan §8-A D1 / WED-BIR 독립 합의): deriving it from the already-filtered
    # `items` would zero out every currently-hidden kind, breaking the
    # legend's "what to turn back on" map. Reuse `items` as-is when no
    # ?type= filter narrowed the query (kinds is None); only re-query
    # unfiltered when a filter is active.
    if kinds is None:
        all_kind_items = items
    else:
        try:
            all_kind_items = list(
                list_user_activity_for_month(request.user, year=year, month=month, kinds=None)
            )
        except Exception:
            logger.exception(
                "Failed to query unfiltered activity kind counts for year=%s month=%s",
                year,
                month,
            )
            all_kind_items = []

    kind_counts = dict.fromkeys(_VISIBLE_ACTIVITY_TYPE_GROUPS, 0)
    for item in all_kind_items:
        group = _visible_activity_group(item.kind)
        if group is not None:
            kind_counts[group] += 1

    items_by_date = defaultdict(list)
    for item in items:
        if _visible_activity_group(item.kind) is None:
            continue
        if item.date is not None:
            items_by_date[item.date].append(item)
        else:
            day = item.start
            while day <= item.end:
                items_by_date[day].append(item)
                day += timedelta(days=1)

    has_any_items = bool(items_by_date)

    try:
        grid = month_grid(year, month)
    except Exception:
        # Same known core.calendar_grid.month_grid gap flagged in
        # event_calendar (year=1/9999 boundary filler cells) — degraded
        # here rather than fixed at the source, out of this change's scope.
        logger.exception(
            "Failed to build activity calendar grid for year=%s month=%s", year, month
        )
        grid = []
        if calendar_error is None:
            calendar_error = "query_failed"

    weeks = [
        [
            {
                "date": cell.date,
                "in_month": cell.in_month,
                "today": cell.date == today,
                "selected": cell.date == selected_date,
                "count": len(items_by_date.get(cell.date, [])),
                "kinds": sorted(
                    {_visible_activity_group(day_item.kind) for day_item in items_by_date.get(cell.date, [])}
                ),
                "items": [
                    {"group": _visible_activity_group(day_item.kind), "label": day_item.label}
                    for day_item in items_by_date.get(cell.date, [])[:2]
                ],
                "more_count": max(0, len(items_by_date.get(cell.date, [])) - 2),
            }
            for cell in week
        ]
        for week in grid
    ]

    selected_items = _build_selected_activity_items(items_by_date.get(selected_date, []))

    prev_year, prev_month_num = _adjacent_month(year, month, -1)
    next_year, next_month_num = _adjacent_month(year, month, 1)

    context = {
        "calendar_error": calendar_error,
        "month_label": f"{year}년 {month}월",
        "weeks": weeks,
        "selected_date": selected_date,
        "selected_items": selected_items,
        "prev_month": f"{prev_year:04d}-{prev_month_num:02d}",
        "next_month": f"{next_year:04d}-{next_month_num:02d}",
        "extra_query": _activity_extra_query(selected_types),
        "selected_types": selected_types,
        "has_any_items": has_any_items,
        "kind_counts": kind_counts,
        "kind_filters": _activity_kind_filters(
            year=year,
            month=month,
            selected_date=selected_date,
            selected_types=selected_types,
            kind_counts=kind_counts,
        ),
        "reset_filter_url": _activity_filter_url(
            year=year, month=month, selected_date=selected_date, types=[]
        ),
        "status_counts": user_status_counts(request.user),
        "q": q,
        "search_no_match": search_no_match,
    }
    return render(request, "core/archive/calendar.html", context)


def _search_activity_date_jump(request, *, q, selected_types):
    """Resolve the activity calendar's ?q= date-jump search (editorial plan
    §4-a-1 / B6): a non-blank `q` searches the user's whole activity history
    (not just the displayed month) and, on a match, returns a PRG-redirect
    response to that date; on no match, returns (None, True) so the caller
    keeps rendering the currently-parsed month/date unchanged (BIR High: the
    caller must not fall back to today just because the search missed).

    "status" is always excluded from what a jump can land on (mirrors
    _visible_activity_group) even when the caller passed no explicit
    selected_types — landing on a date whose only match is a hidden status
    change would show a selected-date section with nothing in it. An active
    type= filter narrows the search the same way it narrows the grid, so a
    jump never surfaces a kind currently hidden by the user's own filter
    (§4-a-1 "필터 상호작용").
    """
    search_group_names = [
        group
        for group in (selected_types or list(_ACTIVITY_TYPE_GROUPS))
        if group != "status"
    ]
    search_kinds = [
        kind for group in search_group_names for kind in _ACTIVITY_TYPE_GROUPS[group]
    ]

    try:
        match_date = find_latest_activity_date_for_query(request.user, q, kinds=search_kinds)
    except Exception:
        logger.exception("Failed to search activity calendar for q=%r", q)
        match_date = None

    if match_date is None:
        return None, True

    redirect_params = [
        ("month", f"{match_date.year:04d}-{match_date.month:02d}"),
        ("date", match_date.isoformat()),
    ]
    redirect_params += [("type", value) for value in selected_types]
    redirect_url = f"{reverse('archive-calendar-page')}?{urlencode(redirect_params)}#selected-date"
    return redirect(redirect_url), False
