# 컬렉션(보유 굿즈) 목록·생성·수정·상세 뷰 모음.
import uuid
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from archive.models import CollectionItem, VisitRecord
from archive.queries import (
    ARCHIVE_COLLECTION_PAGE_SIZE,
    list_user_collection_items,
    list_user_visit_records,
    user_collection_item_filter_values,
    user_collection_item_summary_counts,
    user_collection_item_work_title_facets,
)
from core.vocab import COLLECTION_ITEM_TYPE

from ._helpers import _archive_query, _render_archive_list, _subject_view

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
