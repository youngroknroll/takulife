"""홈, 행사 목록/캘린더/상세 — 공개 행사 열람 뷰 그룹."""

import logging
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from archive.models import UserEventStatus
from archive.queries import (
    list_user_collection_items,
    list_user_unrecorded_visited_statuses,
    list_user_upcoming_planned_events,
    user_collection_item_summary_counts,
    user_interest_count,
    user_interest_event_ids,
    user_visit_record_counts,
)
from core.calendar_grid import month_grid
from core.models import HomeConfig
from core.vocab import (
    ARCHIVE_STATUS_LABELS,
    CATEGORY,
    CATEGORY_LABELS,
    EVENT_SORT,
    EVENT_SORT_LABELS,
    EVENT_STATUS,
    EVENT_STATUS_LABELS,
    REGION,
    REGION_LABELS,
)
from events.models import Event
from events.presenters import derive_event_display
from events.queries import (
    PUBLIC_LISTING_PAGE_SIZE,
    list_published_events,
    list_published_events_for_month,
    parse_public_listing_params,
)

from ._helpers import (
    _adjacent_month,
    _attach_display,
    _parse_calendar_date,
    _parse_calendar_month,
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
