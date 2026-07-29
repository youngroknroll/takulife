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

logger = logging.getLogger(__name__)


def home(request):
    today = timezone.localdate()
    ongoing_qs = list_published_events({"status": "ongoing"}, today=today)
    closing_qs = Event.objects.published().ending_within_days(5, today=today)
    # Sliders drop events whose period has already ended (end_date < today);
    # events without an end_date are kept (cannot be "ended").
    recent_qs = (
        Event.objects.published().exclude(end_date__lt=today).order_by("-id")[:15]
    )

    # "카테고리로 둘러보기" tiles: staff-curated order/selection via HomeConfig.
    # Falls back to all vocab categories when no selection is stored.
    category_counts = {
        row["category"]: row["count"]
        for row in Event.objects.published().values("category").annotate(count=Count("id"))
    }
    category_tiles = [
        {"slug": slug, "label": label, "count": category_counts.get(slug, 0)}
        for slug, label in HomeConfig.get_solo().featured_category_pairs()
    ]

    popular_qs = Event.objects.published().exclude(end_date__lt=today).most_viewed(5)

    context = {
        "ongoing_rows": _attach_display(ongoing_qs[:15], today=today, user=request.user),
        "closing_rows": _attach_display(closing_qs[:15], today=today, user=request.user),
        "recent_rows": _attach_display(recent_qs, today=today, user=request.user),
        "category_tiles": category_tiles,
        "popular_rows": _attach_display(popular_qs, today=today, user=request.user),
    }

    if request.user.is_authenticated:
        user = request.user
        collection_summary = user_collection_item_summary_counts(user)
        recent_goods = list(list_user_collection_items(user)[:5])
        # Built directly rather than via _build_archive_status_rows: that
        # helper reads .derived_status unconditionally (an annotation-only
        # attribute), but this row's status is always "visited" by
        # construction (list_user_unrecorded_visited_statuses already
        # filters to it) — no derivation applies, and _subject_view itself
        # has no derived_status dependency, so the raw slice is safe as-is.
        unrecorded_rows = [
            {"status_id": row.pk, "subject": _subject_view(row)}
            for row in list_user_unrecorded_visited_statuses(user)[:5]
        ]
        upcoming_rows = _attach_display(
            list_user_upcoming_planned_events(user, today=today)[:4],
            today=today,
            user=user,
        )
        context.update(
            {
                "collection_summary": collection_summary,
                # 2026-07-23 에디토리얼 리디자인: 통계가 2칸에서 4칸으로 늘었다.
                # 보유/구함은 collection_summary가 담당하고, 나머지 두 칸은
                # 방문 기록 수와 찜 수. 둘 다 단순 count 쿼리다.
                "snapshot_visit_count": user_visit_record_counts(user)["total_count"],
                "snapshot_interest_count": user_interest_count(user),
                "recent_goods": recent_goods,
                "unrecorded": unrecorded_rows,
                "upcoming_planned": upcoming_rows,
                "snapshot_active": bool(unrecorded_rows)
                or bool(recent_goods)
                or bool(upcoming_rows)
                or (collection_summary["owned_count"] + collection_summary["wanted_count"] > 0),
            }
        )

    return render(request, "core/home.html", context)


def _active_filter_chips(*, q, selected_region, selected_category, selected_status):
    """Human-readable chips summarising the active q/region/category/status
    filters (Eventbrite-style). Shared by event_list and event_calendar so
    both pages derive the same chip labels from the same selections (calendar
    editorial plan §D — no new query, only relabels values the caller already
    parsed)."""
    chips = []
    if q:
        chips.append(f"검색: {q}")
    for region in selected_region:
        chips.append(REGION_LABELS.get(region, region))
    for category in selected_category:
        chips.append(CATEGORY_LABELS.get(category, category))
    if selected_status:
        chips.append(EVENT_STATUS_LABELS.get(selected_status, selected_status))
    return chips


def event_list(request):
    page_obj = None
    total_count = 0
    event_rows = []

    # Invalid / unrecognised filter values are treated as "no match" so the
    # browse page degrades to the empty state ("이벤트 없음") instead of an error
    # screen. The JSON API still rejects the same input with 400.
    try:
        params = parse_public_listing_params(request.GET)
        # Default to "active" (ongoing/upcoming) when the caller sent no
        # status filter. Must stay after parsing, not before: "active" is
        # deliberately absent from STATUS_CHOICES, so injecting it into the
        # raw request.GET would make parse_public_listing_params raise
        # ValidationError, which the except below silently swallows into an
        # empty-state page.
        if not params.get("status"):
            params = {**params, "status": "active"}
        qs = list_published_events(params)
        total_count = qs.count()
        paginator = Paginator(qs, PUBLIC_LISTING_PAGE_SIZE)
        page_obj = paginator.get_page(request.GET.get("page"))
        event_rows = _attach_display(page_obj.object_list, user=request.user)
    except ValidationError:
        pass

    selected_region = request.GET.getlist("region")
    selected_category = request.GET.getlist("category")
    selected_status = request.GET.get("status", "")
    q = request.GET.get("q", "")
    selected_sort = request.GET.get("sort", "")

    # Defensive scalar-wrap left over from an earlier non-QueryDict code path.
    # Unreachable today: getlist(k) is empty iff get(k) is None for the same
    # key, so `not getlist and get` can never hold. Kept (not deleted) but
    # excluded from coverage; safe to remove in a dedicated cleanup.
    if not selected_region and request.GET.get("region"):  # pragma: no cover
        selected_region = [request.GET.get("region")]
    if not selected_category and request.GET.get("category"):  # pragma: no cover
        selected_category = [request.GET.get("category")]

    active_filters = bool(
        q or selected_region or selected_category or selected_status
    )

    # Human-readable chips summarising the active filters (Eventbrite-style).
    active_filter_chips = _active_filter_chips(
        q=q,
        selected_region=selected_region,
        selected_category=selected_category,
        selected_status=selected_status,
    )

    context = {
        "page_obj": page_obj,
        "total_count": total_count,
        "event_rows": event_rows,
        "active_filters": active_filters,
        "active_filter_chips": active_filter_chips,
        # vocab tuples for filter UI
        "CATEGORY": CATEGORY,
        "REGION": REGION,
        "EVENT_STATUS": EVENT_STATUS,
        # Sort moved out of the sidebar filter form and into the results-head
        # toggle menu (2026-07-22), so the template needs the vocab tuple to
        # render one link per option instead of four hardcoded <option>s.
        "EVENT_SORT": EVENT_SORT,
        # current selections
        "q": q,
        "selected_region": selected_region,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "selected_sort": selected_sort,
        "selected_sort_label": EVENT_SORT_LABELS.get(selected_sort, EVENT_SORT_LABELS[""]),
        # List<->calendar toggle link querystring preservation (dual-calendar
        # plan §단계 5) — event_list had no such context before; added here
        # rather than duplicating its own already-working filter extraction.
        "extra_query": _calendar_extra_query(request),
        # List page pager (PR #221 shared pager) needs sort preserved too, so
        # it cannot reuse _calendar_extra_query (which deliberately drops
        # sort for the calendar toggle contract).
        "pager_query": _event_list_pager_query(request),
    }
    return render(request, "core/events/list.html", context)


def _event_list_pager_query(request):
    """Return the current q/region/category/status/sort filters as a
    '&key=value' querystring tail — leading '&', matching
    templates/core/partials/_pager.html's extra_query convention — so the
    same context key can be dropped straight after a '?page=...' value in a
    template. Unlike _calendar_extra_query, this includes 'sort': the events
    list pager must preserve sort order across pages, while the calendar
    toggle link deliberately does not.
    """
    pairs = []
    for key in ("q", "region", "category", "status", "sort"):
        for value in request.GET.getlist(key):
            if value:
                pairs.append((key, value))
    if not pairs:
        return ""
    return "&" + urlencode(pairs)


def _calendar_extra_query(request):
    """Return the current q/region/category/status filters as a '&key=value'
    querystring tail — leading '&', matching
    templates/core/partials/_pager.html's extra_query convention — so the
    same context key can be dropped straight after a '?month=...'/'?page=...'
    value in a template. Deliberately excludes 'sort' and the calendar-only
    'month'/'date' params (dual-calendar service design §6 only requires
    q/region/category/status parity with the existing listing).
    """
    pairs = []
    for key in ("q", "region", "category", "status"):
        for value in request.GET.getlist(key):
            if value:
                pairs.append((key, value))
    if not pairs:
        return ""
    return "&" + urlencode(pairs)


def event_calendar(request):
    """Events calendar SSR view (dual-calendar plan §단계 5 / PR-C).

    Presentation-only: date-range/overlap business rules stay owned by
    events.queries.list_published_events_for_month and
    core.calendar_grid.month_grid — this view only parses request params,
    calls those, and reshapes the results into the template context
    contract below (keys fixed, do not rename — the Frontend
    Implementation Engineer's templates are being built against this exact
    contract in parallel):

    calendar_error (None|"invalid"|"query_failed"), month_label
    ("YYYY년 M월"), weeks (7-cell-per-week list of
    {date, in_month, today, selected, items[{title,url}] (max 2),
    more_count, count}), selected_date, selected_events, prev_month/
    next_month ("YYYY-MM"), extra_query, plus the same filter-panel context
    keys event_list already provides (CATEGORY/REGION/EVENT_STATUS,
    q/selected_region/selected_category/selected_status/selected_sort/
    selected_sort_label) so the existing filter-check markup can be reused
    verbatim.
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

    try:
        params = parse_public_listing_params(request.GET)
    except ValidationError:
        # Same degrade as event_list: an unrecognised/invalid filter value is
        # "no match", never an error screen — independent of calendar_error.
        params = {}

    try:
        events = list(list_published_events_for_month(params, year=year, month=month))
    except Exception:
        logger.exception(
            "Failed to query events calendar for year=%s month=%s", year, month
        )
        events = []
        if calendar_error is None:
            calendar_error = "query_failed"

    events_by_date = defaultdict(list)
    for event in events:
        day = event.start_date
        end = event.end_date or event.start_date
        while day <= end:
            events_by_date[day].append(event)
            day += timedelta(days=1)

    try:
        grid = month_grid(year, month)
    except Exception:
        # core.calendar_grid.month_grid can raise for a month whose leading/
        # trailing filler week would need a date outside year 1..9999 (e.g.
        # year=1/month=1 needs a few December-of-year-0 filler days) — a
        # known gap in the already-merged CAL-4 grid module (its own unit
        # tests only covered year=2026), surfaced by CAL-5-07's extreme-month
        # scenario. Degraded here rather than fixed at the source, which is
        # out of this change's authorized scope; flagged for a follow-up fix
        # to core/calendar_grid.py.
        logger.exception(
            "Failed to build calendar grid for year=%s month=%s", year, month
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
                "items": [
                    {
                        "title": event.title,
                        "url": reverse("event-detail-page", args=[event.id]),
                        "category_slug": event.category,
                    }
                    for event in events_by_date.get(cell.date, [])[:2]
                ],
                "more_count": max(len(events_by_date.get(cell.date, [])) - 2, 0),
                "count": len(events_by_date.get(cell.date, [])),
            }
            for cell in week
        ]
        for week in grid
    ]

    selected_events = _attach_display(
        events_by_date.get(selected_date, []), today=today, user=request.user
    )

    prev_year, prev_month_num = _adjacent_month(year, month, -1)
    next_year, next_month_num = _adjacent_month(year, month, 1)

    selected_region = request.GET.getlist("region")
    selected_category = request.GET.getlist("category")
    selected_status = request.GET.get("status", "")
    q = request.GET.get("q", "")
    selected_sort = request.GET.get("sort", "")

    context = {
        "calendar_error": calendar_error,
        "month_label": f"{year}년 {month}월",
        "weeks": weeks,
        "selected_date": selected_date,
        "selected_events": selected_events,
        "prev_month": f"{prev_year:04d}-{prev_month_num:02d}",
        "next_month": f"{next_year:04d}-{next_month_num:02d}",
        "extra_query": _calendar_extra_query(request),
        "active_filter_chips": _active_filter_chips(
            q=q,
            selected_region=selected_region,
            selected_category=selected_category,
            selected_status=selected_status,
        ),
        # filter-panel context, mirrored verbatim from event_list so its
        # existing filter-check markup can be reused as-is.
        "CATEGORY": CATEGORY,
        "REGION": REGION,
        "EVENT_STATUS": EVENT_STATUS,
        "q": q,
        "selected_region": selected_region,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "selected_sort": selected_sort,
        "selected_sort_label": EVENT_SORT_LABELS.get(selected_sort, EVENT_SORT_LABELS[""]),
        "active_filter_count": len(selected_region)
        + len(selected_category)
        + (1 if selected_status else 0)
        + (1 if q else 0),
    }
    return render(request, "core/events/calendar.html", context)


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


def event_detail(request, event_id):
    event = get_object_or_404(Event.objects.published(), pk=event_id)
    Event.objects.increment_view_count(event.pk)
    display = derive_event_display(event)
    status_slug = display["status"]

    user_status = ""
    user_status_id = None
    user_interested = False
    user_interest_id = None
    if request.user.is_authenticated:
        row = (
            UserEventStatus.objects.filter(user=request.user, event=event)
            .with_derived_status(today=timezone.localdate())
            .values_list("derived_status", "id")
            .first()
        )
        if row:
            user_status, user_status_id = row
        interest_map = user_interest_event_ids(request.user, event_ids=[event.id])
        user_interest_id = interest_map.get(event.id)
        user_interested = user_interest_id is not None

    today = timezone.localdate()
    related_events = _attach_display(
        Event.objects.published().related_to(event, today=today, limit=3),
        today=today,
    )

    context = {
        "event": event,
        "status_slug": status_slug,
        "status_label": EVENT_STATUS_LABELS.get(status_slug, ""),
        "category_label": CATEGORY_LABELS.get(event.category, event.category),
        "region_label": REGION_LABELS.get(event.region, "") if event.region else "",
        "dday": display["dday"],
        "user_status": user_status,
        "user_status_id": user_status_id,
        "user_status_label": ARCHIVE_STATUS_LABELS.get(user_status, ""),
        "user_interested": user_interested,
        "user_interest_id": user_interest_id,
        "related_events": related_events,
    }
    return render(request, "core/events/detail.html", context)


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


SERIES_INK_COUNT = 12
# Must stay coprime with SERIES_INK_COUNT — a shared factor would visit only
# part of the palette and reintroduce collisions well before 12 works.
SERIES_INK_STRIDE = 5


def _series_ink_classes(titles_in_registration_order) -> dict[str, str]:
    """Assign an accent-color bucket ("gi-1".."gi-{SERIES_INK_COUNT}") to
    each work_title by FIRST-REGISTRATION ORDER, not a hash.

    A hash-of-the-string scheme (the previous approach) still collides even
    after growing the bucket count, by the birthday paradox — with
    SERIES_INK_COUNT=12 buckets, just 5 distinct work_titles already have
    roughly a 62% chance that two of them land in the same bucket. Assigning
    by position instead makes collisions mathematically impossible as long
    as the number of distinct work_titles stays within SERIES_INK_COUNT.

    The order must be REGISTRATION order (earliest-first_id first), not
    count-descending display order: sorting by count would make a
    work_title's color shift whenever any item is added anywhere in the
    collection, since that can change the count ranking. Sorting by first
    registration keeps a work_title's color stable for its whole lifetime.

    Consecutive registrations are spread around the hue wheel by
    SERIES_INK_STRIDE rather than taking adjacent buckets. The palette walks
    the hue wheel in order, so bucket N and N+1 are the 30°-apart pair that is
    hardest to tell apart at an 8px dot — and back-to-back registrations are
    exactly the common case. Striding by 5 puts a user's first two works 150°
    apart instead of 30°. The stride is coprime with SERIES_INK_COUNT, so the
    mapping is still a bijection and the no-collision guarantee is untouched.

    Titles beyond SERIES_INK_COUNT wrap back around to "gi-1".
    """
    return {
        title: f"gi-{index * SERIES_INK_STRIDE % SERIES_INK_COUNT + 1}"
        for index, title in enumerate(titles_in_registration_order)
    }


def _collection_item_row(item, series_ink_classes):
    """Display row for one CollectionItem card.

    ``quantity_label``/``tradeable_label`` are "" (no badge) whenever the
    respective count is 0 — a wanted-only item with quantity=0 (D1) renders
    with no numeric badge instead of "수량 0개".

    ``series_ink_classes`` is the {work_title: class} map from
    _series_ink_classes(). A blank work_title is never a key in that map
    (the facet query excludes it), so .get(..., "gi-0") falls through to the
    no-series bucket without a separate blank-check branch here.

    ``badges`` is the fixed-order (owned -> wanted -> tradeable) badge list
    consumed by templates/core/partials/_collection_badges.html. Computed
    once here so the four template consumers never each re-derive
    ``item.quantity > 0`` themselves (that duplication is what hid the
    original owned/wanted axis bug). ``tradeable=True`` implies
    ``owned=True`` at the DB level (tradeable_quantity <= quantity), so the
    "owned False, tradeable True" branch is unreachable and intentionally
    has no code path here.
    """
    owned = item.quantity > 0
    wanted = item.is_wanted
    tradeable = item.tradeable_quantity > 0
    if owned or wanted or tradeable:
        badges = []
        if owned:
            badges.append({"tone": "owned", "label": "보유"})
        if wanted:
            badges.append({"tone": "wanted", "label": "구함"})
        if tradeable:
            badges.append({"tone": "tradeable", "label": "교환"})
    else:
        badges = [{"tone": "none", "label": "미보유"}]

    return {
        "item": item,
        "quantity_label": f"수량 {item.quantity}개" if item.quantity > 0 else "",
        "tradeable_label": (
            f"교환 가능 {item.tradeable_quantity}개" if item.tradeable_quantity > 0 else ""
        ),
        "is_wanted": item.is_wanted,
        "badges": badges,
        "series_ink_class": series_ink_classes.get(item.work_title, "gi-0"),
    }


@login_required
@ensure_csrf_cookie
def archive_collection_items(request):
    # Legacy bookmark compat (2026-07-28): ?is_wanted=false used to BE the
    # owned tab's URL; now that owned is its own axis, a bookmarked
    # ?is_wanted=false link must forward to ?owned=true so it stops
    # under-counting (owned-and-wanted rows used to be excluded). Skipped
    # when owned is already present — an explicit owned value means the
    # caller already made a deliberate choice on the new axis, and this
    # shim must not overwrite it. Placed before any query work since a
    # redirected request has no reason to hit the database.
    if request.GET.get("is_wanted") == "false" and "owned" not in request.GET:
        redirect_params = request.GET.copy()
        del redirect_params["is_wanted"]
        redirect_params["owned"] = "true"
        return redirect(f"{request.path}?{redirect_params.urlencode()}")

    user = request.user
    q = _archive_query(request)
    work_title = request.GET.get("work_title", "")
    character_name = request.GET.get("character_name", "")
    item_type = request.GET.get("item_type", "")
    # Unrecognised values (including absence) mean "no filter" — mirrors the
    # visits/personal-entries filter fallback discipline (500 prevention).
    is_wanted = {"true": True, "false": False}.get(request.GET.get("is_wanted", ""))
    is_wanted_value = {True: "true", False: "false"}.get(is_wanted, "")
    duplicate = {"true": True, "false": False}.get(request.GET.get("duplicate", ""))
    duplicate_value = {True: "true", False: "false"}.get(duplicate, "")
    tradeable = {"true": True, "false": False}.get(request.GET.get("tradeable", ""))
    tradeable_value = {True: "true", False: "false"}.get(tradeable, "")
    owned = {"true": True, "false": False}.get(request.GET.get("owned", ""))
    owned_value = {True: "true", False: "false"}.get(owned, "")
    # Only "list" is recognised; absence or any other value falls back to the
    # default gallery view (same 500-prevention fallback discipline as above).
    view_mode = "list" if request.GET.get("view") == "list" else "gallery"

    summary_counts = user_collection_item_summary_counts(user)
    has_items = summary_counts["total_count"] > 0

    filtered_qs = list_user_collection_items(
        user,
        work_title=work_title,
        character_name=character_name,
        item_type=item_type,
        is_wanted=is_wanted,
        duplicate=duplicate,
        tradeable=tradeable,
        owned=owned,
        q=q,
    )
    paginator = Paginator(filtered_qs, ARCHIVE_COLLECTION_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    # One facet query for the WHOLE collection (not the filtered/paged
    # subset) drives both the sidebar counts and the per-series color
    # palette, so the same work_title always gets the same color no matter
    # which page, filter, or search narrowed the current view.
    work_title_facets = user_collection_item_work_title_facets(user)
    palette_titles = [
        facet["work_title"]
        for facet in sorted(work_title_facets, key=lambda facet: facet["first_id"])
    ]
    series_ink_classes = _series_ink_classes(palette_titles)

    item_rows = [_collection_item_row(item, series_ink_classes) for item in page_obj.object_list]

    # --- Query-string helpers ----------------------------------------------
    # Four DIFFERENT axis subsets, easy to confuse:
    #   chip_query_suffix  — q + 3 filters + view; is_wanted/duplicate/tradeable
    #                        EXCLUDED (they are one exclusive sub-tab axis that
    #                        chips switch between, so a chip must never carry
    #                        the sub-tab that's already active)
    #   pager_query        — all 3 filters + q + view + all 3 sub-tab values
    #                        (paging changes nothing about the active filters)
    #   clear_query_suffix — 3 filters + view + all 3 sub-tab values, q
    #                        EXCLUDED (clear removes only the search term)
    filter_parts = []
    if work_title:
        filter_parts.append(("work_title", work_title))
    if character_name:
        filter_parts.append(("character_name", character_name))
    if item_type:
        filter_parts.append(("item_type", item_type))

    sub_tab_parts = []
    if is_wanted_value:
        sub_tab_parts.append(("is_wanted", is_wanted_value))
    if duplicate_value:
        sub_tab_parts.append(("duplicate", duplicate_value))
    if tradeable_value:
        sub_tab_parts.append(("tradeable", tradeable_value))
    if owned_value:
        sub_tab_parts.append(("owned", owned_value))

    view_parts = [("view", "list")] if view_mode == "list" else []

    chip_parts = list(filter_parts)
    if q:
        chip_parts.append(("q", q))
    chip_parts += view_parts
    chip_query_suffix = "&" + urlencode(chip_parts) if chip_parts else ""

    clear_parts = list(filter_parts) + sub_tab_parts + view_parts
    clear_query_suffix = urlencode(clear_parts)

    pager_parts = list(filter_parts) + sub_tab_parts
    if q:
        pager_parts.append(("q", q))
    pager_parts += view_parts
    pager_query = "&" + urlencode(pager_parts) if pager_parts else ""

    return _render_archive_list(
        request,
        full_template="core/archive/collection.html",
        fragment_template="core/partials/_archive_results_collection.html",
        context={
            "item_rows": item_rows,
            "page_obj": page_obj,
            "has_items": has_items,
            "owned_count": summary_counts["owned_count"],
            "wanted_count": summary_counts["wanted_count"],
            "tradeable_count": summary_counts["tradeable_count"],
            # Same series_ink_classes map the cards use (built once above from
            # the whole collection), so a sidebar dot and the cards it
            # filters to structurally always share one color — the whole
            # point of the per-series coding. work_title_facets is already
            # sorted count-descending by the query layer, so this just
            # relabels it with the display color; no re-sort here.
            "work_title_counts": [
                {
                    "title": facet["work_title"],
                    "count": facet["count"],
                    "series_ink_class": series_ink_classes.get(facet["work_title"], "gi-0"),
                }
                for facet in work_title_facets
            ],
            "filter_values": user_collection_item_filter_values(user),
            "q": q,
            "has_query": bool(q),
            "work_title": work_title,
            "character_name": character_name,
            "item_type": item_type,
            "is_wanted_value": is_wanted_value,
            "duplicate_value": duplicate_value,
            "tradeable_value": tradeable_value,
            "owned_value": owned_value,
            "view_mode": view_mode,
            "chip_query_suffix": chip_query_suffix,
            "pager_query": pager_query,
            "clear_query_suffix": clear_query_suffix,
        },
    )


def _visit_record_option(record):
    """Display option for one selectable/preselected visit record.

    ``label`` combines the visit's subject title and date so the create
    form's dropdown/locked display reads unambiguously even when the same
    subject was visited more than once (collection domain design plan §3-4
    (c): repeat visits are allowed, so titles alone can collide).
    """
    subject = _subject_view(record)
    return {"id": record.pk, "label": f"{subject['title']} · {record.visited_on}"}


def _parse_collection_visit_preselect(request):
    """Resolve an optional ?visit_record=<id> into a locked visit record for
    the collection-item create form.

    Mirrors _parse_visit_preselect's ASCII/digit/length guard against a
    crafted id turning into a 500, but scopes the lookup to VisitRecord rows
    owned by the requester — an id that exists but belongs to another user
    must not lock in their record. Returns None for any invalid, missing, or
    foreign id, so the create form falls back to the selectable dropdown.
    """
    ident = request.GET.get("visit_record", "")
    if not ident.isascii() or not ident.isdigit() or len(ident) > 18:
        return None
    pk = int(ident)
    record = (
        VisitRecord.objects.filter(pk=pk, user=request.user)
        .select_related("event", "personal_entry")
        .first()
    )
    if record is None:
        return None
    return _visit_record_option(record)


@login_required
@ensure_csrf_cookie
def archive_collection_item_create(request):
    """Read-only render: the form posts to the existing collection-item JSON
    API (archive.collection_urls) from a future collection JS module. Event
    is never a user-facing control here — create_collection_item always
    syncs it from visit_record server-side (§3-1 FK-pair invariant), so this
    page must never render a name="event" input.
    """
    # Issued once per form render into a hidden input so the token survives
    # a bfcache DOM snapshot and serves as the replay idempotency key (plan §4-1).
    return render(
        request,
        "core/archive/collection_create.html",
        {
            "selectable_visit_records": list_user_visit_records(request.user),
            "preselect": _parse_collection_visit_preselect(request),
            "COLLECTION_ITEM_TYPE": COLLECTION_ITEM_TYPE,
            "client_token": uuid.uuid4(),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_collection_item_edit(request, item_id):
    """Owner-scoped edit page (404 for another user's item). Mirrors
    archive_collection_item_create: no name="event" control (event stays
    server-synced from visit_record) and no visibility control (§3-1,
    reserved for the future trade opt-in gate).
    """
    item = get_object_or_404(CollectionItem, pk=item_id, user=request.user)
    return render(
        request,
        "core/archive/collection_edit.html",
        {
            "item": item,
            "COLLECTION_ITEM_TYPE": COLLECTION_ITEM_TYPE,
        },
    )


def _collection_item_meta_rows(item):
    """Derived meta headline rows for the read-only detail page.

    Each row is omitted whenever its backing field is empty — the caller
    template renders the whole ``<dl>`` conditionally on this list being
    non-empty (CD-15). The linked-visit row's title prefers the visit's
    Event title, falling back to the PersonalEntry title when the visit has
    no Event, mirroring collection_edit.html:115's existing branch.
    """
    rows = []
    if item.quantity > 0:
        rows.append(
            {"label": "수량", "value": f"{item.quantity}개", "url": None, "lock_hint": False}
        )
    if item.tradeable_quantity > 0:
        rows.append(
            {
                "label": "교환 가능",
                "value": f"{item.tradeable_quantity}개",
                "url": None,
                "lock_hint": False,
            }
        )
    if item.acquired_on:
        rows.append(
            {
                "label": "획득일",
                "value": item.acquired_on.strftime("%Y.%m.%d"),
                "url": None,
                "lock_hint": False,
            }
        )
    if item.acquisition_source:
        rows.append(
            {
                "label": "획득 경로",
                "value": item.acquisition_source,
                "url": None,
                "lock_hint": False,
            }
        )
    visit = item.visit_record
    if visit is not None:
        title = visit.event.title if visit.event else visit.personal_entry.title
        rows.append(
            {
                "label": "연결된 방문 기록",
                "value": f"{title} · {visit.visited_on:%m-%d}",
                "url": f"/archive/visits/{visit.pk}/",
                "lock_hint": True,
            }
        )
    return rows


@login_required
@ensure_csrf_cookie
def archive_collection_item_detail(request, item_id):
    """Read-only detail page for one CollectionItem (owner-scoped).

    Shares the whole-collection color palette with archive_collection_items
    (built from user_collection_item_work_title_facets, sorted by
    first_id) rather than computing a single-item palette — a work_title's
    color bucket must be identical whether the user is viewing the list or
    one item's detail page (CD-14).
    """
    item = get_object_or_404(
        CollectionItem.objects.select_related(
            "visit_record__event", "visit_record__personal_entry"
        ),
        pk=item_id,
        user=request.user,
    )
    work_title_facets = user_collection_item_work_title_facets(request.user)
    palette_titles = [
        facet["work_title"]
        for facet in sorted(work_title_facets, key=lambda facet: facet["first_id"])
    ]
    series_ink_classes = _series_ink_classes(palette_titles)
    return render(
        request,
        "core/archive/collection_detail.html",
        {
            "item": item,
            "row": _collection_item_row(item, series_ink_classes),
            "meta_rows": _collection_item_meta_rows(item),
            "tradeable_quantity": item.tradeable_quantity,
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
