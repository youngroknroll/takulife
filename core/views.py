from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from archive.models import UserEventStatus
from archive.queries import (
    ARCHIVE_STATUS_SLUGS,
    list_user_statuses,
    list_user_visit_records,
    user_status_counts,
)
from core.vocab import (
    ARCHIVE_STATUS,
    ARCHIVE_STATUS_LABELS,
    CATEGORY,
    CATEGORY_LABELS,
    EVENT_STATUS,
    EVENT_STATUS_LABELS,
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


def _attach_display(events, *, today=None):
    """Attach derived display (status_slug, status_label, dday) to each event.

    Returns a list of plain dicts so templates can use dot notation cleanly.
    """
    result = []
    for event in events:
        display = derive_event_display(event, today=today)
        status_slug = display["status"]
        result.append(
            {
                "event": event,
                "status_slug": status_slug,
                "status_label": EVENT_STATUS_LABELS.get(status_slug, ""),
                "category_label": CATEGORY_LABELS.get(event.category, event.category),
                "dday": display["dday"],
            }
        )
    return result


def home(request):
    ongoing_qs = list_published_events({"status": "ongoing"})
    closing_qs = list_published_events({"status": "closing_soon"})
    recent_qs = Event.objects.published().order_by("-id")[:6]

    context = {
        "project_name": "takulife",
        "ongoing_events": _attach_display(ongoing_qs[:6]),
        "closing_events": _attach_display(closing_qs[:5]),
        "recent_events": _attach_display(recent_qs),
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
        event_rows = _attach_display(page_obj.object_list)

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

    context = {
        "project_name": "takulife",
        "page_obj": page_obj,
        "total_count": total_count,
        "event_rows": event_rows,
        "validation_error": validation_error,
        "active_filters": active_filters,
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
    }
    return render(request, "core/event_list.html", context)


def event_detail(request, event_id):
    event = get_object_or_404(Event.objects.published(), pk=event_id)
    display = derive_event_display(event)
    status_slug = display["status"]
    context = {
        "project_name": "takulife",
        "event": event,
        "status_slug": status_slug,
        "status_label": EVENT_STATUS_LABELS.get(status_slug, ""),
        "category_label": CATEGORY_LABELS.get(event.category, event.category),
        "dday": display["dday"],
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
    return render(
        request,
        "core/archive.html",
        {
            "project_name": "takulife",
            "status_rows": status_rows,
            "has_statuses": len(status_rows) > 0,
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
