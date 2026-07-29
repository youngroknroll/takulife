"""내 활동(아카이브) — 상태·방문 기록·직접 등록·찜 목록 뷰 모음."""

import uuid
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from archive.models import PersonalEntry, VisitRecord
from archive.queries import (
    ARCHIVE_INTEREST_PAGE_SIZE,
    ARCHIVE_PERSONAL_PAGE_SIZE,
    ARCHIVE_RECORD_PAGE_SIZE,
    ARCHIVE_STATUS_PAGE_SIZE,
    ARCHIVE_STATUS_SLUGS,
    ARCHIVE_VISIT_PAGE_SIZE,
    list_items_acquired_at_visit,
    list_user_interests,
    list_user_personal_entries,
    list_user_planned_events,
    list_user_statuses,
    list_user_visit_records,
    user_interest_summary_counts,
    user_personal_entry_counts,
    user_personal_interest_ids,
    user_personal_statuses,
    user_status_counts,
    user_visit_category_values,
    user_visit_record_counts,
)
from core.vocab import (
    ARCHIVE_INTEREST_SORT,
    ARCHIVE_INTEREST_SORT_LABELS,
    ARCHIVE_PERSONAL_SORT,
    ARCHIVE_PERSONAL_SORT_LABELS,
    ARCHIVE_STATUS,
    ARCHIVE_STATUS_SORT,
    ARCHIVE_STATUS_SORT_LABELS,
    ARCHIVE_VISIT_SORT,
    ARCHIVE_VISIT_SORT_LABELS,
    archive_status_label,
    CATEGORY_LABELS,
    PERSONAL_ENTRY_CATEGORY_SUGGESTIONS,
)
from events.models import Event

from ._helpers import _archive_query, _attach_display, _render_archive_list, _subject_view
from .collection import _collection_item_row, _series_ink_classes


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
