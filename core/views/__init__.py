import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import OperationalError, connection
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from archive.models import ActivityLogEntry, CollectionItem, PersonalEntry, UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_COLLECTION_PAGE_SIZE,
    ARCHIVE_INTEREST_PAGE_SIZE,
    ARCHIVE_PERSONAL_PAGE_SIZE,
    ARCHIVE_RECORD_PAGE_SIZE,
    ARCHIVE_STATUS_PAGE_SIZE,
    ARCHIVE_STATUS_SLUGS,
    ARCHIVE_VISIT_PAGE_SIZE,
    GOODS_ACQUIRED_KIND,
    SCHEDULE_KIND,
    VISIT_KIND,
    find_latest_activity_date_for_query,
    list_items_acquired_at_visit,
    list_user_activity_for_month,
    list_user_collection_items,
    list_user_interests,
    list_user_personal_entries,
    list_user_planned_events,
    list_user_statuses,
    list_user_unrecorded_visited_statuses,
    list_user_upcoming_planned_events,
    list_user_visit_records,
    user_collection_item_filter_values,
    user_collection_item_summary_counts,
    user_collection_item_work_title_facets,
    user_interest_count,
    user_interest_event_ids,
    user_interest_summary_counts,
    user_personal_entry_counts,
    user_personal_interest_ids,
    user_personal_statuses,
    user_status_counts,
    user_visit_category_values,
    user_visit_record_counts,
)
from core.calendar_grid import default_selected_date, month_grid
from core.models import HomeConfig
from core.vocab import (
    ARCHIVE_INTEREST_SORT,
    ARCHIVE_INTEREST_SORT_LABELS,
    ARCHIVE_PERSONAL_SORT,
    ARCHIVE_PERSONAL_SORT_LABELS,
    ARCHIVE_STATUS,
    ARCHIVE_STATUS_LABELS,
    ARCHIVE_STATUS_SORT,
    ARCHIVE_STATUS_SORT_LABELS,
    ARCHIVE_VISIT_SORT,
    ARCHIVE_VISIT_SORT_LABELS,
    archive_status_label,
    CATEGORY,
    CATEGORY_LABELS,
    COLLECTION_ITEM_TYPE,
    EVENT_SORT,
    EVENT_SORT_LABELS,
    EVENT_STATUS,
    EVENT_STATUS_LABELS,
    PERSONAL_ENTRY_CATEGORY_SUGGESTIONS,
    REGION,
    REGION_LABELS,
)
from events.models import Event
from events.presenters import derive_event_display, is_recently_added
from events.queries import (
    PUBLIC_LISTING_PAGE_SIZE,
    list_published_events,
    list_published_events_for_month,
    parse_public_listing_params,
)

from ._helpers import (
    _adjacent_month,
    _archive_query,
    _attach_display,
    _parse_calendar_date,
    _parse_calendar_month,
    _render_archive_list,
    _subject_view,
)
from .collection import (
    _collection_item_row,
    _series_ink_classes,
    archive_collection_item_create,
    archive_collection_item_detail,
    archive_collection_item_edit,
    archive_collection_items,
)
from .events import event_calendar, event_detail, event_list, home

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Activity calendar (dual-calendar plan §단계 5 / PR-D). Grouped here with
# event_calendar (rather than beside the other archive/* views further down)
# because it reuses that function's month/date parsing helpers, grid
# builder, and query-failure guard pattern directly — the URL prefix is
# archive/, but the implementation is part of the same calendar feature.
# ---------------------------------------------------------------------------

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


def _build_archive_status_rows(user_statuses):
    """Build display rows for archive status entries (official or unofficial).

    Returns dicts carrying status_id/slug/label plus a uniform, null-safe
    ``subject`` view so the template renders an Event and a PersonalEntry the
    same way (with a 비공식 marker for the latter).
    """
    rows = []
    for us in user_statuses:
        subject = _subject_view(us)
        rows.append(
            {
                "status_id": us.pk,
                "status_slug": us.derived_status,
                "status_label": archive_status_label(us.derived_status),
                "label_visited": archive_status_label("visited"),
                "label_planned": archive_status_label("planned"),
                "subject": subject,
                "updated_at": us.updated_at,
                "review_text": us.review_text,
                "visit_record_id": us.visit_record_id,
            }
        )
    return rows


def _archive_status_context(
    user, selected_status, *, page_size, page_number, q: str = "", sort: str = ""
):
    """Build the shared context for the archive dashboard and statuses pages.

    Both pages derive 'missed' identically via the shared read helper (instead
    of reading raw stored status); the summary counts stay unfiltered (aggregate
    across all statuses). Invalid status filters fall back to "" (all).

    The status list is paginated (``page_size`` rows per page) so only the
    current page's rows are built into the heavier display dicts. The two pages
    pass different sizes (기록장 10 vs 예정 목록 5). ``has_statuses`` reflects the
    total match count, not the current page, so the empty state shows only when
    the user genuinely has none. ``pager_query`` preserves the status filter,
    q param, and sort across page links.

    ``q`` narrows the status list server-side (title/location search). Summary
    counts (status_counts) always reflect the unfiltered totals.
    ``has_any`` signals that the user owns at least one status of any kind,
    independent of the current filter; this lets templates distinguish an
    empty-filter result from a genuinely empty archive.

    ``sort`` selects list_user_statuses' ordering; an unrecognized value falls
    back to "" (the default ordering) the same way an unrecognized status
    falls back to "" (all).

    ``sort_query`` (via _archive_sort_link_query) is a separate status/q-only
    tail for the sort <details> menu's own links; unlike pager_query/
    search_suffix above it excludes 'sort' and 'page' so a new sort value
    doesn't get overwritten by the old one still in the tail.
    """
    if selected_status not in ARCHIVE_STATUS_SLUGS:
        selected_status = ""
    if sort not in ARCHIVE_STATUS_SORT_LABELS:
        sort = ""

    qs = list_user_statuses(user, selected_status, q=q, sort=sort)
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page_number)
    status_rows = _build_archive_status_rows(page_obj.object_list)

    parts = []
    if selected_status:
        parts.append(("status", selected_status))
    if q:
        parts.append(("q", q))
    if sort:
        parts.append(("sort", sort))
    pager_query = "&" + urlencode(parts) if parts else ""
    # Tail that filter chips append to preserve the active search across a
    # filter switch (urlencoded so 한글/space/& are safe; the template escapes
    # the leading & to &amp; in the href, which the browser decodes).
    search_suffix_parts = [("q", q)] if q else []
    if sort:
        search_suffix_parts.append(("sort", sort))
    search_suffix = "&" + urlencode(search_suffix_parts) if search_suffix_parts else ""
    sort_query = _archive_sort_link_query(selected_status, q)

    counts = user_status_counts(user)
    return {
        "status_rows": status_rows,
        "page_obj": page_obj,
        "pager_query": pager_query,
        "search_suffix": search_suffix,
        "has_statuses": paginator.count > 0,
        "has_any": sum(counts.values()) > 0,
        "status_counts": counts,
        "selected_status": selected_status,
        "ARCHIVE_STATUS": ARCHIVE_STATUS,
        "q": q,
        "has_query": bool(q),
        "selected_sort": sort,
        "selected_sort_label": ARCHIVE_STATUS_SORT_LABELS[sort],
        "ARCHIVE_STATUS_SORT": ARCHIVE_STATUS_SORT,
        "sort_query": sort_query,
    }


def _archive_sort_link_query(selected_status, q):
    """Return the current status/q filters as a '&key=value' querystring
    tail — leading '&', matching templates/core/partials/_pager.html's
    extra_query convention — for the archive sort <details> menu's
    '?sort=<value>...' links to append.

    Deliberately excludes 'sort' and 'page', unlike _archive_status_context's
    own pager_query/search_suffix (which intentionally include 'sort' because
    they must preserve the active ordering across pagination/search). A sort
    link already starts with '?sort=<new value>', so reusing pager_query's
    tail here would duplicate the 'sort' key
    (?sort=NEW&status=...&sort=OLD); QueryDict.get() returns the last value,
    silently discarding the new sort. Excluding 'page' means picking a new
    sort resets the list to page 1, mirroring _calendar_extra_query's
    exclusion of its own page-like params for the same reason.
    """
    parts = []
    if selected_status:
        parts.append(("status", selected_status))
    if q:
        parts.append(("q", q))
    return "&" + urlencode(parts) if parts else ""


@login_required
@ensure_csrf_cookie
def archive(request):
    context = _archive_status_context(
        request.user,
        request.GET.get("status", ""),
        page_size=ARCHIVE_RECORD_PAGE_SIZE,
        page_number=request.GET.get("page"),
        q=_archive_query(request),
        sort=request.GET.get("sort", ""),
    )
    return _render_archive_list(
        request,
        full_template="core/archive/index.html",
        fragment_template="core/partials/_archive_results_record.html",
        context=context,
    )


@login_required
@ensure_csrf_cookie
def archive_statuses(request):
    context = _archive_status_context(
        request.user,
        request.GET.get("status", ""),
        page_size=ARCHIVE_STATUS_PAGE_SIZE,
        page_number=request.GET.get("page"),
        q=_archive_query(request),
        sort=request.GET.get("sort", ""),
    )
    return _render_archive_list(
        request,
        full_template="core/archive/statuses.html",
        fragment_template="core/partials/_archive_results_statuses.html",
        context=context,
    )


@login_required
@ensure_csrf_cookie
def archive_visits(request):
    user = request.user
    q = _archive_query(request)
    raw_filter = request.GET.get("filter", "")
    sort = request.GET.get("sort", "")
    if sort not in ARCHIVE_VISIT_SORT_LABELS:
        sort = ""

    # --- Category chips derived from the user's FULL visit history --------
    # Using the whole dataset (not just the current page) guarantees chips are
    # stable across pages. Labels are resolved here so archive/queries.py stays
    # free of any core.vocab import (prevents circular dependency).
    pairs = user_visit_category_values(user)
    categories = []
    seen_labels: set = set()
    for event_cat, personal_cat in pairs:
        if event_cat:
            label = CATEGORY_LABELS.get(event_cat, event_cat)
        elif personal_cat:
            label = personal_cat
        else:
            continue
        if label not in seen_labels:
            categories.append(label)
            seen_labels.add(label)
    # Determine axis presence by checking which FK is null in the pair — the
    # event__category column is None when there is no event (unofficial), and
    # personal_entry__category is None when there is no personal_entry (official).
    # Using None-identity (not truthiness) avoids false negatives when an
    # official event has an empty category string.
    has_unofficial = any(event_cat is None for event_cat, _ in pairs)
    has_official = any(personal_cat is None for _, personal_cat in pairs)

    # --- Filter parsing with whitelist check ------------------------------
    # Unrecognised values fall back to no-filter (500 prevention).
    official = None
    category_codes: tuple = ()
    category_label = ""

    if raw_filter == "unofficial":
        official = False
    elif raw_filter.startswith("cat:"):
        label = raw_filter[4:]
        if label and label in categories:
            category_label = label
            category_codes = tuple(
                code for code, lbl in CATEGORY_LABELS.items() if lbl == label
            )
        # else: empty label or label not in whitelist → no-filter fallback

    selected_filter = raw_filter if (official is not None or category_label) else ""

    # --- Summary counts from the unfiltered base -------------------------
    # These always report the user's total visit history, independent of any
    # active filter, so the summary cards never confusingly shrink.
    visit_counts = user_visit_record_counts(user)
    total_count = visit_counts["total_count"]
    memo_count = visit_counts["memo_count"]

    # --- Filtered + paginated result set ----------------------------------
    filtered_qs = list_user_visit_records(
        user,
        official=official,
        category_codes=category_codes,
        category_label=category_label,
        q=q,
        sort=sort,
    )
    paginator = Paginator(filtered_qs, ARCHIVE_VISIT_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    visit_rows = [
        {
            "record_id": record.pk,
            "visited_on": record.visited_on,
            "short_review": record.short_review,
            "subject": _subject_view(record),
            "photos": list(record.photos.all()),
        }
        for record in page_obj.object_list
    ]

    # --- Pager query string -----------------------------------------------
    parts = []
    if selected_filter:
        parts.append(("filter", selected_filter))
    if q:
        parts.append(("q", q))
    if sort:
        parts.append(("sort", sort))
    pager_query = "&" + urlencode(parts) if parts else ""
    # Tail filter chips append to keep the active search when switching filters.
    search_suffix_parts = [("q", q)] if q else []
    if sort:
        search_suffix_parts.append(("sort", sort))
    search_suffix = "&" + urlencode(search_suffix_parts) if search_suffix_parts else ""

    return _render_archive_list(
        request,
        full_template="core/archive/visits.html",
        fragment_template="core/partials/_archive_results_visits.html",
        context={
            "visit_rows": visit_rows,
            "page_obj": page_obj,
            "total_count": total_count,
            "memo_count": memo_count,
            "has_visits": total_count > 0,
            "categories": categories,
            "has_unofficial": has_unofficial,
            "has_official": has_official,
            "selectable_events": list_user_planned_events(user),
            "selectable_personal_entries": list_user_personal_entries(
                user, kind=PersonalEntry.Kind.PLACE
            ),
            "q": q,
            "has_query": bool(q),
            "selected_filter": selected_filter,
            "pager_query": pager_query,
            "search_suffix": search_suffix,
            "selected_sort": sort,
            "selected_sort_label": ARCHIVE_VISIT_SORT_LABELS[sort],
            "ARCHIVE_VISIT_SORT": ARCHIVE_VISIT_SORT,
        },
    )


def _parse_visit_preselect(request):
    """Resolve an optional ?subject=event:<id> / personal:<id> into a locked
    subject for the visit-create form.

    Returns ``{"value": "event:5", "label": "이벤트명"}`` when the param points at a
    published event or one of the requester's own personal entries; ``None``
    otherwise (the form then falls back to the selectable dropdown). This lets a
    '기록' button on an already-visited event — which is not in the planned-only
    dropdown — still write a record, since the visit API accepts any published
    event. The id is validated here, so the template can render it as a trusted
    locked field.
    """
    kind, _, ident = request.GET.get("subject", "").partition(":")
    # Guard against non-ASCII "digits" (int() rejects them) and oversized ids
    # (a pk past the DB integer range raises on the ORM lookup) — both would
    # otherwise turn a crafted ?subject= into a 500.
    if not ident.isascii() or not ident.isdigit() or len(ident) > 18:
        return None
    pk = int(ident)
    if kind == "event":
        event = Event.objects.published().filter(pk=pk).first()
        if event is not None:
            return {"value": f"event:{event.pk}", "label": event.title}
    elif kind == "personal":
        entry = PersonalEntry.objects.filter(
            pk=pk, user=request.user, kind=PersonalEntry.Kind.PLACE
        ).first()
        if entry is not None:
            return {"value": f"personal:{entry.pk}", "label": entry.title}
    return None


@login_required
@ensure_csrf_cookie
def archive_visit_create(request):
    """Dedicated write page for creating a visit record.

    Read-only render: the form posts to the existing JSON/photo APIs from
    visit_create.js. Subject choices mirror the inline form they replace, except
    when ``?subject=`` preselects a specific subject (e.g. from a 방문 완료 이벤트's
    '기록' button) — then the form shows that subject locked instead of the
    dropdown.
    """
    # Issued once per form render into a hidden input so the token survives
    # a bfcache DOM snapshot and serves as the replay idempotency key (plan §4-1).
    return render(
        request,
        "core/archive/visit_create.html",
        {
            "selectable_events": list_user_planned_events(request.user),
            "selectable_personal_entries": list_user_personal_entries(
                request.user, kind=PersonalEntry.Kind.PLACE
            ),
            "preselect": _parse_visit_preselect(request),
            "client_token": uuid.uuid4(),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_visit_edit(request, record_id):
    """Edit page for one visit record (owner-scoped).

    Pre-fills date/memo and lists existing photos; edits happen via the PATCH /
    photo APIs from visit_edit.js. Subject is shown read-only.
    """
    record = get_object_or_404(VisitRecord, pk=record_id, user=request.user)
    return render(
        request,
        "core/archive/visit_edit.html",
        {
            "record_id": record.pk,
            "subject": _subject_view(record),
            "visited_on": record.visited_on,
            "short_review": record.short_review,
            "photos": list(record.photos.all().order_by("id")),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_visit_detail(request, record_id):
    """Read-only detail page for one visit record (owner-scoped).

    Shows the visit's subject, date, memo, photos, and the CollectionItems
    acquired at that visit (archive/queries.list_items_acquired_at_visit) —
    an intra-archive reverse-FK read, no new cross-domain coupling.
    ``@ensure_csrf_cookie`` is required here (not just on the edit page)
    because the page's delete action needs the CSRF cookie set.
    """
    record = get_object_or_404(VisitRecord, pk=record_id, user=request.user)
    goods = list_items_acquired_at_visit(record)
    series_ink_classes = _series_ink_classes([item.work_title for item in goods])
    return render(
        request,
        "core/archive/visit_detail.html",
        {
            "record_id": record.pk,
            "subject": _subject_view(record),
            "visited_on": record.visited_on,
            "short_review": record.short_review,
            "photos": list(record.photos.all().order_by("id")),
            "goods_rows": [_collection_item_row(item, series_ink_classes) for item in goods],
            "goods_count": len(goods),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_personal_entries(request):
    user = request.user
    q = _archive_query(request)
    sort = request.GET.get("sort", "")
    if sort not in ARCHIVE_PERSONAL_SORT_LABELS:
        sort = ""

    # Summary counts always come from the unfiltered set so the header cards
    # report the user's total collection, independent of any active search.
    entry_counts = user_personal_entry_counts(user)
    total_count = entry_counts["total_count"]
    visit_linked_count = entry_counts["visit_linked_count"]
    has_entries = total_count > 0

    # Page queryset is filtered by q (if provided) and then paginated.
    page_qs = list_user_personal_entries(user, q=q, sort=sort)
    paginator = Paginator(page_qs, ARCHIVE_PERSONAL_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    interest_map = user_personal_interest_ids(user)
    status_map = user_personal_statuses(user)

    entry_rows = []
    for entry in page_obj.object_list:
        status_slug, status_id = status_map.get(entry.id, ("", None))
        entry_rows.append(
            {
                "entry": entry,
                "is_place": entry.kind == PersonalEntry.Kind.PLACE,
                "interest_id": interest_map.get(entry.id),
                "status_slug": status_slug,
                "status_id": status_id,
                "status_label": archive_status_label(status_slug) if status_slug else "",
                "planned_label": archive_status_label("planned"),
                "is_submitted": entry.promotion_status == PersonalEntry.PromotionStatus.SUBMITTED,
            }
        )

    # Pager query string preserves both an active search and a non-default
    # sort — mirrors archive_visits' parts-list pattern above.
    parts = []
    if q:
        parts.append(("q", q))
    if sort:
        parts.append(("sort", sort))
    pager_query = "&" + urlencode(parts) if parts else ""

    return _render_archive_list(
        request,
        full_template="core/archive/personal_entries.html",
        fragment_template="core/partials/_archive_results_personal.html",
        context={
            "entry_rows": entry_rows,
            "total_count": total_count,
            "visit_linked_count": visit_linked_count,
            "has_entries": has_entries,
            "page_obj": page_obj,
            "pager_query": pager_query,
            "q": q,
            "has_query": bool(q),
            "selected_sort": sort,
            "selected_sort_label": ARCHIVE_PERSONAL_SORT_LABELS[sort],
            "ARCHIVE_PERSONAL_SORT": ARCHIVE_PERSONAL_SORT,
        },
    )


@login_required
@ensure_csrf_cookie
def archive_personal_entry_create(request):
    """Read-only render: the form posts to the existing personal-entries JSON
    API (`/api/personal-entries/`), not a new endpoint — mirrors
    archive_collection_item_create's render-only shape. Context carries
    PERSONAL_ENTRY_CATEGORY_SUGGESTIONS as free-input hint chips (not a
    `choices` constraint — the field stays free text)."""
    # Issued once per form render into a hidden input so the token survives
    # a bfcache DOM snapshot and serves as the replay idempotency key (plan §4-1).
    return render(
        request,
        "core/archive/personal_create.html",
        {
            "PERSONAL_ENTRY_CATEGORY_SUGGESTIONS": PERSONAL_ENTRY_CATEGORY_SUGGESTIONS,
            "client_token": uuid.uuid4(),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_interests(request):
    user = request.user
    q = _archive_query(request)
    sort = request.GET.get("sort", "")
    if sort not in ARCHIVE_INTEREST_SORT_LABELS:
        sort = ""

    # --- Summary counts from the unfiltered base ---------------------------
    # Always describe the user's full 찜 set, independent of any active
    # search — mirrors the sibling tabs' summary-card behavior (§1 D2/D3, V5).
    counts = user_interest_summary_counts(user)
    interest_count = counts["interest_count"]
    ongoing_count = counts["ongoing_count"]
    planned_overlap_count = counts["planned_overlap_count"]

    # --- Filtered + paginated result set ------------------------------------
    filtered_qs = list_user_interests(user, q=q, sort=sort)
    paginator = Paginator(filtered_qs, ARCHIVE_INTEREST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_interests = list(page_obj.object_list)

    # Official (event-linked) rows are batched through _attach_display once
    # (not per-row, which would be N+1) and mapped back by event id.
    official_events = [
        interest.event for interest in page_interests if interest.event_id
    ]
    display_by_event_id = {
        display["event"].id: display
        for display in _attach_display(official_events, user=user)
    }

    interest_rows = []
    for interest in page_interests:
        if interest.event_id:
            display = display_by_event_id[interest.event_id]
            user_status = display["user_status"]
            interest_rows.append(
                {
                    "interest_id": interest.pk,
                    "subject": _subject_view(interest),
                    "status": display["status_slug"],
                    "dday": display["dday"],
                    "user_status": user_status,
                    # §1 D1: only offer 방문 예정 when the viewer has no
                    # status on this event yet — a shared status button on an
                    # already-tracked row (e.g. 방문 완료) would otherwise
                    # silently overwrite that existing record. Also exclude
                    # already-ended events — planning a visit to an event
                    # that is already over is meaningless, and the design
                    # never shows this button on an ended row.
                    "can_plan": user_status == "" and display["status_slug"] != "ended",
                }
            )
        else:
            interest_rows.append(
                {
                    "interest_id": interest.pk,
                    "subject": _subject_view(interest),
                    "status": None,
                    "dday": None,
                    "user_status": None,
                    "can_plan": False,
                }
            )

    # --- Pager query string --------------------------------------------------
    parts = []
    if q:
        parts.append(("q", q))
    if sort:
        parts.append(("sort", sort))
    pager_query = "&" + urlencode(parts) if parts else ""

    return _render_archive_list(
        request,
        full_template="core/archive/interests.html",
        fragment_template="core/partials/_archive_results_interests.html",
        context={
            "interest_rows": interest_rows,
            "interest_count": interest_count,
            "ongoing_count": ongoing_count,
            "planned_overlap_count": planned_overlap_count,
            "has_interests": interest_count > 0,
            "page_obj": page_obj,
            "q": q,
            "has_query": bool(q),
            "pager_query": pager_query,
            "selected_sort": sort,
            "selected_sort_label": ARCHIVE_INTEREST_SORT_LABELS[sort],
            "ARCHIVE_INTEREST_SORT": ARCHIVE_INTEREST_SORT,
        },
    )


@login_required
def mypage(request):
    user = request.user
    saved_count = sum(user_status_counts(user).values())
    visit_count = user_visit_record_counts(user)["total_count"]
    personal_entry_count = user_personal_entry_counts(user)["total_count"]
    interest_count = user_interest_count(user)
    collection_count = user_collection_item_summary_counts(user)["total_count"]

    # index_rows drives mypage.html's index list; row order and ink values
    # are fixed by the mypage brief (§1). Each row is rendered as a single
    # <a> spanning the whole row, so its accessible name concatenates
    # title + badge + description + count. Whenever the title already
    # contains the badge label, keep domain_label empty below so the
    # template's "{% if row.domain_label %}" skips a badge that would
    # otherwise repeat the title for screen readers (BIR M3; exact-match
    # "내 활동"/"내 활동" is just the special case of this rule).
    index_rows = [
        {
            "title": "내 컬렉션",
            "domain_label": "컬렉션",
            "ink": "brand",
            "description": "모은 굿즈를 한눈에 확인해요",
            "count": collection_count,
            "unit": "점",
            "url": "/collection/",
        },
        {
            "title": "내 활동",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "저장한 행사를 모아봐요",
            "count": saved_count,
            "unit": "건",
            "url": "/archive/",
        },
        {
            "title": "다녀온 기록",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "다녀온 행사를 기록해요",
            "count": visit_count,
            "unit": "건",
            "url": "/archive/visits/",
        },
        {
            "title": "직접 등록",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "비공식 장소·행사를 등록해요",
            "count": personal_entry_count,
            "unit": "곳",
            "url": "/archive/personal/",
        },
        {
            "title": "찜 목록",
            "domain_label": "내 활동",
            "ink": "pink",
            "description": "관심 있는 행사를 찜해요",
            "count": interest_count,
            "unit": "건",
            "url": "/archive/interests/",
        },
    ]
    for row in index_rows:
        if row["domain_label"] and row["domain_label"] in row["title"]:
            row["domain_label"] = ""

    password_changed_at = user.password_changed_at
    password_changed_display = (
        timezone.localtime(password_changed_at).strftime("%Y.%m.%d")
        if password_changed_at is not None
        else "변경 이력 없음"
    )

    return render(
        request,
        "core/mypage.html",
        {
            "saved_count": saved_count,
            "visit_count": visit_count,
            "personal_entry_count": personal_entry_count,
            "interest_count": interest_count,
            "collection_count": collection_count,
            "joined_year": user.date_joined.year,
            "password_changed_at": password_changed_at,
            "password_changed_display": password_changed_display,
            "index_rows": index_rows,
        },
    )


def legal_privacy(request):
    return render(request, "core/legal/privacy.html")


def legal_terms(request):
    return render(request, "core/legal/terms.html")


@api_view(["GET"])
def api_root(request):
    return Response({"name": "takulife API"})


@api_view(["GET"])
def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return Response({"status": "error"}, status=503)
    return Response({"status": "ok"})
