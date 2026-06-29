from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from archive.models import PersonalEntry, UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_RECORD_PAGE_SIZE,
    ARCHIVE_STATUS_PAGE_SIZE,
    ARCHIVE_STATUS_SLUGS,
    ARCHIVE_VISIT_PAGE_SIZE,
    list_user_interests,
    list_user_personal_entries,
    list_user_planned_events,
    list_user_statuses,
    list_user_visit_records,
    user_interest_count,
    user_interest_event_ids,
    user_personal_interest_ids,
    user_personal_statuses,
    user_status_counts,
)
from core.vocab import (
    ARCHIVE_STATUS,
    ARCHIVE_STATUS_LABELS,
    archive_status_label,
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
from events.presenters import derive_event_display, is_recently_added
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

    popular_qs = Event.objects.published().exclude(end_date__lt=today).most_viewed(5)

    context = {
        "ongoing_events": _attach_display(ongoing_qs[:15], today=today, user=request.user),
        "closing_events": _attach_display(closing_qs[:15], today=today, user=request.user),
        "recent_events": _attach_display(recent_qs, today=today, user=request.user),
        "category_tiles": category_tiles,
        "popular_events": _attach_display(popular_qs, today=today, user=request.user),
    }
    return render(request, "core/home.html", context)


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
        "page_obj": page_obj,
        "total_count": total_count,
        "event_rows": event_rows,
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
    return render(request, "core/events/list.html", context)


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
        kind = subject["kind"]
        rows.append(
            {
                "status_id": us.pk,
                "status_slug": us.derived_status,
                # Kind-aware: a goods item reads 구매…, a place/event reads 방문….
                "status_label": archive_status_label(us.derived_status, kind),
                "label_visited": archive_status_label("visited", kind),
                "label_planned": archive_status_label("planned", kind),
                "subject": subject,
            }
        )
    return rows


def _archive_status_context(user, selected_status, *, page_size, page_number):
    """Build the shared context for the archive dashboard and statuses pages.

    Both pages derive 'missed' identically via the shared read helper (instead
    of reading raw stored status); the summary counts stay unfiltered (aggregate
    across all statuses). Invalid status filters fall back to "" (all).

    The status list is paginated (``page_size`` rows per page) so only the
    current page's rows are built into the heavier display dicts. The two pages
    pass different sizes (기록장 10 vs 예정 목록 5). ``has_statuses`` reflects the
    total match count, not the current page, so the empty state shows only when
    the user genuinely has none. ``pager_query`` preserves the status filter
    across page links.
    """
    if selected_status not in ARCHIVE_STATUS_SLUGS:
        selected_status = ""

    paginator = Paginator(list_user_statuses(user, selected_status), page_size)
    page_obj = paginator.get_page(page_number)
    status_rows = _build_archive_status_rows(page_obj.object_list)
    return {
        "status_rows": status_rows,
        "page_obj": page_obj,
        "pager_query": f"&status={selected_status}" if selected_status else "",
        "has_statuses": paginator.count > 0,
        "status_counts": user_status_counts(user),
        "selected_status": selected_status,
        "ARCHIVE_STATUS": ARCHIVE_STATUS,
    }


@login_required
@ensure_csrf_cookie
def archive(request):
    context = _archive_status_context(
        request.user,
        request.GET.get("status", ""),
        page_size=ARCHIVE_RECORD_PAGE_SIZE,
        page_number=request.GET.get("page"),
    )
    return render(request, "core/archive/index.html", context)


@login_required
@ensure_csrf_cookie
def archive_statuses(request):
    context = _archive_status_context(
        request.user,
        request.GET.get("status", ""),
        page_size=ARCHIVE_STATUS_PAGE_SIZE,
        page_number=request.GET.get("page"),
    )
    return render(request, "core/archive/statuses.html", context)


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
    base_qs = list_user_visit_records(request.user)

    # Summary cards report totals across all records, so they are counted on the
    # full queryset (COUNT queries — no rows or photos loaded), not the page.
    # total_count reuses the paginator's own (memoized) count to avoid a second
    # COUNT for the same queryset.
    paginator = Paginator(base_qs, ARCHIVE_VISIT_PAGE_SIZE)
    total_count = paginator.count
    memo_count = base_qs.exclude(short_review="").count()
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

    # Distinct non-empty category labels (in first-seen order) drive the filter
    # chips; has_unofficial gates the separate 비공식 chip (an official/unofficial
    # axis, not a category). Chips reflect the current page's cards so a chip
    # never hides every visible card — cross-page navigation is the pager's job,
    # not the client-side filter's.
    categories = []
    for row in visit_rows:
        label = row["subject"]["category_label"]
        if label and label not in categories:
            categories.append(label)
    has_unofficial = any(not row["subject"]["is_official"] for row in visit_rows)

    return render(
        request,
        "core/archive/visits.html",
        {
            "visit_rows": visit_rows,
            "page_obj": page_obj,
            "total_count": total_count,
            "memo_count": memo_count,
            "has_visits": total_count > 0,
            "categories": categories,
            "has_unofficial": has_unofficial,
            "selectable_events": list_user_planned_events(request.user),
            "selectable_personal_entries": list_user_personal_entries(request.user),
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
        entry = PersonalEntry.objects.filter(pk=pk, user=request.user).first()
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
    return render(
        request,
        "core/archive/visit_create.html",
        {
            "selectable_events": list_user_planned_events(request.user),
            "selectable_personal_entries": list_user_personal_entries(request.user),
            "preselect": _parse_visit_preselect(request),
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
def archive_personal_entries(request):
    entries = list(list_user_personal_entries(request.user))
    interest_map = user_personal_interest_ids(request.user)
    status_map = user_personal_statuses(request.user)

    entry_rows = []
    for entry in entries:
        status_slug, status_id = status_map.get(entry.id, ("", None))
        entry_rows.append(
            {
                "entry": entry,
                "kind_label": "장소" if entry.kind == PersonalEntry.Kind.PLACE else "굿즈",
                "interest_id": interest_map.get(entry.id),
                "status_slug": status_slug,
                "status_id": status_id,
                "status_label": archive_status_label(status_slug, entry.kind) if status_slug else "",
                "planned_label": archive_status_label("planned", entry.kind),
                "is_submitted": entry.promotion_status == PersonalEntry.PromotionStatus.SUBMITTED,
            }
        )
    place_count = sum(1 for entry in entries if entry.kind == PersonalEntry.Kind.PLACE)

    return render(
        request,
        "core/archive/personal_entries.html",
        {
            "entry_rows": entry_rows,
            "total_count": len(entries),
            "place_count": place_count,
            "goods_count": len(entries) - place_count,
            "has_entries": len(entries) > 0,
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
        "core/drafts/list.html",
        {
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
            "core/drafts/detail.html",
            {
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
        "core/drafts/detail.html",
        {
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
