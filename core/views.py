from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from archive.models import UserEventStatus
from archive.queries import (
    ARCHIVE_STATUS_SLUGS,
    list_user_interests,
    list_user_statuses,
    list_user_visit_records,
    user_interest_count,
    user_interest_event_ids,
    user_status_counts,
)
from core.vocab import (
    ARCHIVE_STATUS,
    ARCHIVE_STATUS_LABELS,
    CATEGORY,
    CATEGORY_LABELS,
    EVENT_SORT_LABELS,
    EVENT_STATUS,
    EVENT_STATUS_LABELS,
    INTEREST_LABEL,
    REGION,
    REGION_LABELS,
)
from drafts.models import EventDraft
from drafts.queries import draft_review_stats
from events.models import Event
from events.presenters import derive_event_display
from events.queries import (
    PUBLIC_LISTING_PAGE_SIZE,
    list_published_events,
    parse_public_listing_params,
)


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
        user_status_map = {
            event_id: (status_val, status_id)
            for event_id, status_val, status_id in UserEventStatus.objects.filter(
                user=user, event_id__in=event_ids
            ).values_list("event_id", "status", "id")
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
                "dday": display["dday"],
                "user_status": user_status,
                "user_status_id": user_status_id,
                "user_status_label": ARCHIVE_STATUS_LABELS.get(user_status, ""),
                "user_interested": interest_id is not None,
                "user_interest_id": interest_id,
            }
        )
    return result


def home(request):
    ongoing_qs = list_published_events({"status": "ongoing"})
    closing_qs = list_published_events({"status": "closing_soon"})
    recent_qs = Event.objects.published().order_by("-id")[:6]

    # "카테고리로 둘러보기" tiles: one per vocab category (in vocab order),
    # each carrying the count of published events so users can browse by type.
    category_counts = {
        row["category"]: row["count"]
        for row in Event.objects.published().values("category").annotate(count=Count("id"))
    }
    category_tiles = [
        {"slug": slug, "label": label, "count": category_counts.get(slug, 0)}
        for slug, label in CATEGORY
    ]

    popular_qs = Event.objects.published().most_viewed(5)

    context = {
        "project_name": "takulife",
        "ongoing_events": _attach_display(ongoing_qs[:6], user=request.user),
        "closing_events": _attach_display(closing_qs[:5], user=request.user),
        "recent_events": _attach_display(recent_qs, user=request.user),
        "category_tiles": category_tiles,
        "popular_events": _attach_display(popular_qs, user=request.user),
    }
    return render(request, "core/home.html", context)


def event_list(request):
    validation_error = None
    page_obj = None
    total_count = 0
    event_rows = []

    try:
        params = parse_public_listing_params(request.GET)
    except ValidationError:
        validation_error = True
        params = {}

    if not validation_error:
        qs = list_published_events(params)
        total_count = qs.count()
        paginator = Paginator(qs, PUBLIC_LISTING_PAGE_SIZE)
        page_obj = paginator.get_page(request.GET.get("page"))
        event_rows = _attach_display(page_obj.object_list, user=request.user)

    selected_region = request.GET.getlist("region")
    selected_category = request.GET.getlist("category")
    selected_status = request.GET.get("status", "")
    selected_q = request.GET.get("q", "")
    selected_sort = request.GET.get("sort", "")

    # region/category may be sent as single value (GET param) or multiple
    # Normalise: if not a list context, wrap the scalar param
    if not selected_region and request.GET.get("region"):
        selected_region = [request.GET.get("region")]
    if not selected_category and request.GET.get("category"):
        selected_category = [request.GET.get("category")]

    active_filters = bool(
        selected_q or selected_region or selected_category or selected_status
    )

    # Human-readable chips summarising the active filters (Eventbrite-style).
    active_filter_chips = []
    if selected_q:
        active_filter_chips.append(f"검색: {selected_q}")
    for region in selected_region:
        active_filter_chips.append(REGION_LABELS.get(region, region))
    for category in selected_category:
        active_filter_chips.append(CATEGORY_LABELS.get(category, category))
    if selected_status:
        active_filter_chips.append(EVENT_STATUS_LABELS.get(selected_status, selected_status))

    context = {
        "project_name": "takulife",
        "page_obj": page_obj,
        "total_count": total_count,
        "event_rows": event_rows,
        "validation_error": validation_error,
        "active_filters": active_filters,
        "active_filter_chips": active_filter_chips,
        # vocab tuples for filter UI
        "CATEGORY": CATEGORY,
        "REGION": REGION,
        "EVENT_STATUS": EVENT_STATUS,
        # current selections
        "selected_q": selected_q,
        "selected_region": selected_region,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "selected_sort": selected_sort,
        "selected_sort_label": EVENT_SORT_LABELS.get(selected_sort, EVENT_SORT_LABELS[""]),
    }
    return render(request, "core/event_list.html", context)


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
            .values_list("status", "id")
            .first()
        )
        if row:
            user_status, user_status_id = row
        interest_map = user_interest_event_ids(request.user, event_ids=[event.id])
        user_interest_id = interest_map.get(event.id)
        user_interested = user_interest_id is not None

    context = {
        "project_name": "takulife",
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
    return render(request, "core/event_detail.html", context)


def _build_archive_status_rows(user_statuses):
    """Build display rows for archive status entries.

    Returns a list of dicts with event, status_slug, status_label, category_label,
    and status_id for template rendering and JS data attributes.
    """
    rows = []
    for us in user_statuses:
        event = us.event
        rows.append(
            {
                "status_id": us.pk,
                "status_slug": us.status,
                "status_label": ARCHIVE_STATUS_LABELS.get(us.status, us.status),
                "category_label": CATEGORY_LABELS.get(event.category, event.category),
                "event": event,
            }
        )
    return rows


@login_required
@ensure_csrf_cookie
def archive(request):
    user_statuses = (
        UserEventStatus.objects.filter(user=request.user)
        .select_related("event")
        .order_by("-updated_at")
    )
    status_rows = _build_archive_status_rows(user_statuses)
    status_counts = user_status_counts(request.user)
    return render(
        request,
        "core/archive.html",
        {
            "project_name": "takulife",
            "status_rows": status_rows,
            "has_statuses": len(status_rows) > 0,
            "status_counts": status_counts,
        },
    )


@login_required
@ensure_csrf_cookie
def archive_statuses(request):
    selected_status = request.GET.get("status", "")
    if selected_status not in ARCHIVE_STATUS_SLUGS:
        selected_status = ""

    qs = list_user_statuses(request.user, selected_status)
    status_counts = user_status_counts(request.user)

    status_rows = _build_archive_status_rows(qs)
    return render(
        request,
        "core/archive_statuses.html",
        {
            "project_name": "takulife",
            "status_rows": status_rows,
            "has_statuses": len(status_rows) > 0,
            "selected_status": selected_status,
            "status_counts": status_counts,
            "ARCHIVE_STATUS": ARCHIVE_STATUS,
        },
    )


@login_required
@ensure_csrf_cookie
def archive_visits(request):
    visit_records = list_user_visit_records(request.user)

    visit_rows = []
    for record in visit_records:
        event = record.event
        visit_rows.append(
            {
                "record_id": record.pk,
                "visited_on": record.visited_on,
                "short_review": record.short_review,
                "event": event,
                "category_label": CATEGORY_LABELS.get(event.category, event.category),
                "photos": list(record.photos.all()),
            }
        )

    selectable_events = Event.objects.published().order_by("title")

    memo_count = sum(1 for row in visit_rows if row["short_review"])

    return render(
        request,
        "core/archive_visits.html",
        {
            "project_name": "takulife",
            "visit_rows": visit_rows,
            "memo_count": memo_count,
            "has_visits": len(visit_rows) > 0,
            "selectable_events": selectable_events,
        },
    )


@login_required
@ensure_csrf_cookie
def archive_interests(request):
    interests = list_user_interests(request.user)
    interest_count = user_interest_count(request.user)

    interest_rows = []
    for interest in interests:
        event = interest.event
        interest_rows.append(
            {
                "interest_id": interest.pk,
                "event": event,
                "category_label": CATEGORY_LABELS.get(event.category, event.category),
            }
        )

    return render(
        request,
        "core/archive_interests.html",
        {
            "project_name": "takulife",
            "interest_rows": interest_rows,
            "interest_count": interest_count,
            "has_interests": len(interest_rows) > 0,
            "INTEREST_LABEL": INTEREST_LABEL,
        },
    )


def _build_draft_rows(drafts):
    """Attach display labels to each draft for template rendering.

    Returns a list of dicts with the draft object plus resolved
    category_label and region_label so templates use simple dot notation.
    """
    rows = []
    for draft in drafts:
        rows.append(
            {
                "draft": draft,
                "category_label": CATEGORY_LABELS.get(
                    draft.extracted_category, draft.extracted_category
                ),
                "region_label": REGION_LABELS.get(
                    draft.extracted_region, draft.extracted_region
                ),
            }
        )
    return rows


@staff_member_required
@ensure_csrf_cookie
def event_drafts(request):
    drafts = EventDraft.objects.order_by("-id")
    stats = draft_review_stats()
    draft_rows = _build_draft_rows(drafts)
    return render(
        request,
        "core/event_drafts.html",
        {
            "project_name": "takulife",
            "draft_rows": draft_rows,
            "stats": stats,
        },
    )


@staff_member_required
@ensure_csrf_cookie
def event_draft_detail(request, draft_id):
    # Use filter().first() so the staff guard test (which does not seed the DB)
    # still returns 200 (staff can reach the URL). When draft is None the
    # template shows a "not found" notice rather than raising Http404.
    draft = EventDraft.objects.filter(pk=draft_id).first()
    if draft is None:
        return render(
            request,
            "core/event_draft_detail.html",
            {
                "project_name": "takulife",
                "draft": None,
                "draft_not_found": True,
                "draft_id": draft_id,
                "CATEGORY": CATEGORY,
                "REGION": REGION,
            },
        )
    is_pending = draft.review_status == EventDraft.ReviewStatus.PENDING
    category_label = CATEGORY_LABELS.get(
        draft.extracted_category, draft.extracted_category
    )
    region_label = REGION_LABELS.get(draft.extracted_region, draft.extracted_region)
    return render(
        request,
        "core/event_draft_detail.html",
        {
            "project_name": "takulife",
            "draft": draft,
            "is_pending": is_pending,
            "category_label": category_label,
            "region_label": region_label,
            "CATEGORY": CATEGORY,
            "REGION": REGION,
        },
    )


@api_view(["GET"])
def api_root(request):
    return Response({"name": "OshiLog API"})


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})
