import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import OperationalError, connection
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from archive.models import ActivityLogEntry, CollectionItem, PersonalEntry, UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_COLLECTION_PAGE_SIZE,
    ARCHIVE_PERSONAL_PAGE_SIZE,
    ARCHIVE_RECORD_PAGE_SIZE,
    ARCHIVE_STATUS_PAGE_SIZE,
    ARCHIVE_STATUS_SLUGS,
    ARCHIVE_VISIT_PAGE_SIZE,
    GOODS_ACQUIRED_KIND,
    SCHEDULE_KIND,
    VISIT_KIND,
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
    user_interest_count,
    user_interest_event_ids,
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
    ARCHIVE_STATUS,
    ARCHIVE_STATUS_LABELS,
    archive_status_label,
    CATEGORY,
    CATEGORY_LABELS,
    COLLECTION_ITEM_TYPE,
    EVENT_SORT,
    EVENT_SORT_LABELS,
    EVENT_STATUS,
    EVENT_STATUS_LABELS,
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

logger = logging.getLogger(__name__)


def _archive_query(request) -> str:
    """Extract and normalise the ?q= search term from the request.

    Strips surrounding whitespace and truncates at 100 characters so an
    arbitrarily long q value never inflates query time or causes errors.
    """
    return (request.GET.get("q") or "").strip()[:100]


def _attach_display(events, *, today=None, user=None):
    """Attach derived display (status_slug, status_label, dday) to each event.

    When ``user`` is an authenticated user, also attaches ``user_status`` — the
    user's own archive status slug for that event ("" if none) — so discovery
    cards can reflect real state instead of a fixed default.

    Returns a list of plain dicts so templates can use dot notation cleanly.
    """
    events = list(events)
    event_ids = [event.id for event in events]

    user_status_map = {}
    user_interest_map = {}
    if user is not None and user.is_authenticated and events:
        status_today = today if today is not None else timezone.localdate()
        user_status_map = {
            event_id: (status_val, status_id)
            for event_id, status_val, status_id in (
                UserEventStatus.objects.filter(user=user, event_id__in=event_ids)
                .with_derived_status(today=status_today)
                .values_list("event_id", "derived_status", "id")
            )
        }
        user_interest_map = user_interest_event_ids(user, event_ids=event_ids)

    result = []
    for event in events:
        display = derive_event_display(event, today=today)
        status_slug = display["status"]
        user_status, user_status_id = user_status_map.get(event.id, ("", None))
        interest_id = user_interest_map.get(event.id)
        result.append(
            {
                "event": event,
                "status_slug": status_slug,
                "status_label": EVENT_STATUS_LABELS.get(status_slug, ""),
                "category_label": CATEGORY_LABELS.get(event.category, event.category),
                "category_slug": event.category,
                "region_label": REGION_LABELS.get(event.region, "") if event.region else "",
                "dday": display["dday"],
                "is_new": is_recently_added(event, today=today),
                "user_status": user_status,
                "user_status_id": user_status_id,
                "user_status_label": ARCHIVE_STATUS_LABELS.get(user_status, ""),
                "user_interested": interest_id is not None,
                "user_interest_id": interest_id,
            }
        )
    return result


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
    # browse page degrades to the empty state ("행사 없음") instead of an error
    # screen. The JSON API still rejects the same input with 400.
    try:
        params = parse_public_listing_params(request.GET)
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
    }
    return render(request, "core/events/list.html", context)


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


def _adjacent_month(year, month, delta):
    """Return the (year, month) `delta` months away from (year, month),
    wrapping across year boundaries (delta is typically -1 or +1)."""
    total = year * 12 + (month - 1) + delta
    new_year, new_month0 = divmod(total, 12)
    return new_year, new_month0 + 1


def _parse_calendar_month(raw_month, *, today):
    """Parse the ?month=YYYY-MM param. Returns (year, month, error) where
    error is None on success or "invalid" on a malformed/out-of-range value.

    Only a truly *absent* key (raw_month is None) defaults to today's month
    (service design §11.1: "month 부재는 오류가 아니며 당월을 표시한다") —
    a key that is *present* with a blank value (?month=) is itself a format
    error ("month 형식 오류(...,빈 값)는... 오류 패널"), not "absent". The
    caller must pass request.GET.get("month") with no default so this
    function can see that distinction; collapsing both cases to "" here
    would silently treat `?month=` the same as no `month` key at all.
    """
    if raw_month is None:
        return today.year, today.month, None
    try:
        parsed = datetime.strptime(raw_month, "%Y-%m")
    except ValueError:
        return None, None, "invalid"
    return parsed.year, parsed.month, None


def _parse_calendar_date(raw_date, *, year, month, today):
    """Parse the ?date=YYYY-MM-DD param against the already-resolved
    (year, month). Returns (date, error) where error is None on success or
    "invalid" for a malformed value, a nonexistent calendar date, or a date
    outside the displayed month (service design §11.1).

    Only a truly *absent* key (raw_date is None) falls back to
    CAL-4-04/05's default-selection rule — a *present* blank value
    (?date=) is a format error, mirroring _parse_calendar_month's same
    absent-vs-blank distinction. The caller must pass
    request.GET.get("date") with no default.
    """
    if raw_date is None:
        return default_selected_date(year=year, month=month, today=today), None
    try:
        parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return None, "invalid"
    if (parsed.year, parsed.month) != (year, month):
        return None, "invalid"
    return parsed, None


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
        group = _KIND_TO_ACTIVITY_TYPE_GROUP.get(item.kind)
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
    selected, count, kinds} — no per-item titles, dots only), selected_date,
    selected_items (list of {group, label, url, date_text} — sourced from
    archive.queries.CalendarActivityItem's label/url/time_text fields, see
    _build_selected_activity_items), prev_month/next_month, extra_query
    (type= only, month/date excluded),
    selected_types, has_any_items (whole displayed month, under the current
    type filter — see completion report for why this simplification was
    chosen over an always-unfiltered second query).

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

    has_any_items = bool(items)

    items_by_date = defaultdict(list)
    for item in items:
        if item.date is not None:
            items_by_date[item.date].append(item)
        else:
            day = item.start
            while day <= item.end:
                items_by_date[day].append(item)
                day += timedelta(days=1)

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
                    {
                        group
                        for day_item in items_by_date.get(cell.date, [])
                        if (group := _KIND_TO_ACTIVITY_TYPE_GROUP.get(day_item.kind)) is not None
                    }
                ),
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
        "active_filter_count": len(selected_types),
    }
    return render(request, "core/archive/calendar.html", context)


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

    context = {
        "event": event,
        "status_slug": status_slug,
        "status_label": EVENT_STATUS_LABELS.get(status_slug, ""),
        "category_label": CATEGORY_LABELS.get(event.category, event.category),
        "dday": display["dday"],
        "user_status": user_status,
        "user_status_id": user_status_id,
        "user_status_label": ARCHIVE_STATUS_LABELS.get(user_status, ""),
        "user_interested": user_interested,
        "user_interest_id": user_interest_id,
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
            }
        )
    return rows


def _archive_status_context(user, selected_status, *, page_size, page_number, q: str = ""):
    """Build the shared context for the archive dashboard and statuses pages.

    Both pages derive 'missed' identically via the shared read helper (instead
    of reading raw stored status); the summary counts stay unfiltered (aggregate
    across all statuses). Invalid status filters fall back to "" (all).

    The status list is paginated (``page_size`` rows per page) so only the
    current page's rows are built into the heavier display dicts. The two pages
    pass different sizes (기록장 10 vs 예정 목록 5). ``has_statuses`` reflects the
    total match count, not the current page, so the empty state shows only when
    the user genuinely has none. ``pager_query`` preserves the status filter
    and q param across page links.

    ``q`` narrows the status list server-side (title/location search). Summary
    counts (status_counts) always reflect the unfiltered totals.
    ``has_any`` signals that the user owns at least one status of any kind,
    independent of the current filter; this lets templates distinguish an
    empty-filter result from a genuinely empty archive.
    """
    if selected_status not in ARCHIVE_STATUS_SLUGS:
        selected_status = ""

    qs = list_user_statuses(user, selected_status, q=q)
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page_number)
    status_rows = _build_archive_status_rows(page_obj.object_list)

    parts = []
    if selected_status:
        parts.append(("status", selected_status))
    if q:
        parts.append(("q", q))
    pager_query = "&" + urlencode(parts) if parts else ""
    # Tail that filter chips append to preserve the active search across a
    # filter switch (urlencoded so 한글/space/& are safe; the template escapes
    # the leading & to &amp; in the href, which the browser decodes).
    search_suffix = "&" + urlencode([("q", q)]) if q else ""

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
    }


def _render_archive_list(request, *, full_template, fragment_template, context):
    """Render an archive list page, or just its results fragment for live search.

    When the request carries ``?partial=1`` the live-search JS only wants the
    swappable results region (list + empty states + pager), so the fragment
    template is rendered alone instead of the full page. The calling view's
    auth/CSRF decorators still apply — this is an internal branch, not a
    separate unauthenticated endpoint. Any other value (or none) renders the
    full page, so the no-JS GET form keeps working unchanged.
    """
    template = fragment_template if request.GET.get("partial") == "1" else full_template
    return render(request, template, context)


@login_required
@ensure_csrf_cookie
def archive(request):
    context = _archive_status_context(
        request.user,
        request.GET.get("status", ""),
        page_size=ARCHIVE_RECORD_PAGE_SIZE,
        page_number=request.GET.get("page"),
        q=_archive_query(request),
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
    )
    return _render_archive_list(
        request,
        full_template="core/archive/statuses.html",
        fragment_template="core/partials/_archive_results_statuses.html",
        context=context,
    )


def _subject_view(obj):
    """Uniform, null-safe view of an archive row's subject — an official Event
    or an unofficial PersonalEntry.

    Any archive row that carries the subject pattern (VisitRecord, EventInterest,
    UserEventStatus) exposes ``event``/``event_id`` and ``personal_entry``; this
    collapses both into one dict so templates and JS never branch on which FK is
    set. ``subject_type``/``subject_id`` drive the API payload; ``detail_url`` is
    empty for private items (no public page); period dates are None for goods.
    """
    if obj.event_id is not None:
        event = obj.event
        return {
            "title": event.title,
            "category_label": CATEGORY_LABELS.get(event.category, event.category),
            "category_slug": event.category,
            "location": event.location_name,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "is_official": True,
            "kind": "",
            "subject_type": "event",
            "subject_id": event.id,
            "detail_url": f"/events/{event.id}/",
        }
    entry = obj.personal_entry
    return {
        "title": entry.title,
        "category_label": entry.category,
        "location": entry.location_name,
        "start_date": None,
        "end_date": None,
        "is_official": False,
        "kind": entry.kind,
        "subject_type": "personal",
        "subject_id": entry.id,
        "detail_url": "",
    }


@login_required
@ensure_csrf_cookie
def archive_visits(request):
    user = request.user
    q = _archive_query(request)
    raw_filter = request.GET.get("filter", "")

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
    pager_query = "&" + urlencode(parts) if parts else ""
    # Tail filter chips append to keep the active search when switching filters.
    search_suffix = "&" + urlencode([("q", q)]) if q else ""

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
        },
    )


def _parse_visit_preselect(request):
    """Resolve an optional ?subject=event:<id> / personal:<id> into a locked
    subject for the visit-create form.

    Returns ``{"value": "event:5", "label": "행사명"}`` when the param points at a
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
    when ``?subject=`` preselects a specific subject (e.g. from a 방문 완료 행사's
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


def _collection_item_row(item):
    """Display row for one CollectionItem card.

    ``quantity_label``/``tradeable_label`` are "" (no badge) whenever the
    respective count is 0 — a wanted-only item with quantity=0 (D1) renders
    with no numeric badge instead of "수량 0개".
    """
    return {
        "item": item,
        "quantity_label": f"수량 {item.quantity}개" if item.quantity > 0 else "",
        "tradeable_label": (
            f"교환 가능 {item.tradeable_quantity}개" if item.tradeable_quantity > 0 else ""
        ),
        "is_wanted": item.is_wanted,
    }


@login_required
@ensure_csrf_cookie
def archive_collection_items(request):
    user = request.user
    q = _archive_query(request)
    work_title = request.GET.get("work_title", "")
    character_name = request.GET.get("character_name", "")
    item_type = request.GET.get("item_type", "")
    # Unrecognised values (including absence) mean "no filter" — mirrors the
    # visits/personal-entries filter fallback discipline (500 prevention).
    is_wanted = {"true": True, "false": False}.get(request.GET.get("is_wanted", ""))
    is_wanted_value = {True: "true", False: "false"}.get(is_wanted, "")

    summary_counts = user_collection_item_summary_counts(user)
    has_items = (summary_counts["owned_count"] + summary_counts["wanted_count"]) > 0

    filtered_qs = list_user_collection_items(
        user,
        work_title=work_title,
        character_name=character_name,
        item_type=item_type,
        is_wanted=is_wanted,
        q=q,
    )
    paginator = Paginator(filtered_qs, ARCHIVE_COLLECTION_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    item_rows = [_collection_item_row(item) for item in page_obj.object_list]

    # --- Query-string helpers ----------------------------------------------
    # Three DIFFERENT axis subsets, easy to confuse:
    #   chip_query_suffix  — q + 3 filters, is_wanted EXCLUDED (chips switch it)
    #   pager_query        — all 5 axes (paging changes nothing)
    #   clear_query_suffix — is_wanted + 3 filters, q EXCLUDED (clear removes it)
    filter_parts = []
    if work_title:
        filter_parts.append(("work_title", work_title))
    if character_name:
        filter_parts.append(("character_name", character_name))
    if item_type:
        filter_parts.append(("item_type", item_type))

    chip_parts = list(filter_parts)
    if q:
        chip_parts.append(("q", q))
    chip_query_suffix = "&" + urlencode(chip_parts) if chip_parts else ""

    clear_parts = list(filter_parts)
    if is_wanted_value:
        clear_parts.append(("is_wanted", is_wanted_value))
    clear_query_suffix = urlencode(clear_parts)

    pager_parts = list(filter_parts)
    if is_wanted_value:
        pager_parts.append(("is_wanted", is_wanted_value))
    if q:
        pager_parts.append(("q", q))
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
            "filter_values": user_collection_item_filter_values(user),
            "q": q,
            "has_query": bool(q),
            "work_title": work_title,
            "character_name": character_name,
            "item_type": item_type,
            "is_wanted_value": is_wanted_value,
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


@login_required
@ensure_csrf_cookie
def archive_personal_entries(request):
    user = request.user
    q = _archive_query(request)

    # Summary counts always come from the unfiltered set so the header cards
    # report the user's total collection, independent of any active search.
    total_count = user_personal_entry_counts(user)["total_count"]
    has_entries = total_count > 0

    # Page queryset is filtered by q (if provided) and then paginated.
    page_qs = list_user_personal_entries(user, q=q)
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

    pager_query = "&" + urlencode([("q", q)]) if q else ""

    return _render_archive_list(
        request,
        full_template="core/archive/personal_entries.html",
        fragment_template="core/partials/_archive_results_personal.html",
        context={
            "entry_rows": entry_rows,
            "total_count": total_count,
            "has_entries": has_entries,
            "page_obj": page_obj,
            "pager_query": pager_query,
            "q": q,
            "has_query": bool(q),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_interests(request):
    interests = list_user_interests(request.user)
    interest_count = user_interest_count(request.user)

    interest_rows = []
    for interest in interests:
        interest_rows.append(
            {
                "interest_id": interest.pk,
                "subject": _subject_view(interest),
            }
        )

    return render(
        request,
        "core/archive/interests.html",
        {
                "interest_rows": interest_rows,
            "interest_count": interest_count,
            "has_interests": len(interest_rows) > 0,
        },
    )


@login_required
def mypage(request):
    user = request.user
    return render(
        request,
        "core/mypage.html",
        {
            "saved_count": sum(user_status_counts(user).values()),
            "visit_count": user_visit_record_counts(user)["total_count"],
            "personal_entry_count": user_personal_entry_counts(user)["total_count"],
            "interest_count": user_interest_count(user),
            "collection_count": user_collection_item_summary_counts(user)["owned_count"],
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
