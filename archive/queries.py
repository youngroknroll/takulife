"""Read layer for the archive domain.

Reusable query logic for user event statuses, event interests, and visit records.
Query/aggregate logic lives here, not in the view layer — mirrors
drafts/queries.py.
"""
import calendar
from dataclasses import dataclass
# Aliased (not `from datetime import date`): a dataclass field below is also
# named `date`, and for `field: T = default` Python binds the default value
# to the field name *before* evaluating the annotation `T` at class-body
# scope — an unaliased same-named import would already be rebound to `None`
# by the time its own annotation tried to reference it.
from datetime import date as _date

from django.db.models import Count, Exists, Max, Min, OuterRef, Q, Subquery
from django.urls import reverse
from django.utils import timezone

from events.models import Event

from .models import (
    ActivityLogEntry,
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
)

# Canonical archive status slugs, sourced from the model's own choices so the
# set has a single source of truth. Excludes "interested" (now EventInterest).
ARCHIVE_STATUS_SLUGS: tuple[str, ...] = tuple(UserEventStatus.Status.values)

# Page sizes for the archive SSR list pages (rendered by core.views). Kept here
# beside the list queries they bound, mirroring events.queries.PUBLIC_LISTING_PAGE_SIZE.
ARCHIVE_RECORD_PAGE_SIZE = 10  # 기록장 (/archive/) — 저장한 이벤트
ARCHIVE_STATUS_PAGE_SIZE = 5  # 예정 목록 (/archive/statuses/)
ARCHIVE_VISIT_PAGE_SIZE = 5  # 방문 기록 (/archive/visits/)
ARCHIVE_PERSONAL_PAGE_SIZE = 5  # 비공식 목록 (/archive/personal/)
ARCHIVE_COLLECTION_PAGE_SIZE = 10  # 컬렉션 목록 (/collection/)
ARCHIVE_INTEREST_PAGE_SIZE = 10  # 찜 목록 (/archive/interests/)

# Sort slugs for list_user_interests, mapped to their order_by field. "" (the
# default) is the pre-existing -id ordering (최근 찜순), listed explicitly here
# so .get(sort, ARCHIVE_INTEREST_SORT_ORDERING[""]) has a single source for the
# default instead of a duplicated literal — mirrors ARCHIVE_VISIT_SORT_ORDERING.
ARCHIVE_INTEREST_SORT_ORDERING: dict[str, str] = {
    "": "-id",
    "oldest": "id",
}

# Sort slugs for list_user_statuses, mapped to their order_by field. "" (the
# default) is the pre-existing -updated_at ordering, kept unlisted here so an
# unknown/missing slug falls back to it via .get(sort, default) with no
# explicit "" entry needed. Only axes with a plain column on UserEventStatus
# are offered — cross-table axes (e.g. event.start_date) would need an
# annotate and are out of scope.
ARCHIVE_STATUS_SORT_ORDERING: dict[str, str] = {
    "created_at": "-created_at",
}

# Sort slugs for list_user_visit_records, mapped to their order_by tuple.
# "" (the default) is the pre-existing -visited_on, -id ordering, listed
# explicitly here (unlike ARCHIVE_STATUS_SORT_ORDERING above) so
# .get(sort, ARCHIVE_VISIT_SORT_ORDERING[""]) has a single source for the
# default instead of a duplicated literal.
ARCHIVE_VISIT_SORT_ORDERING: dict[str, tuple[str, str]] = {
    "": ("-visited_on", "-id"),
    "oldest": ("visited_on", "id"),
}

# Sort slugs for list_user_personal_entries, mapped to their order_by tuple.
# Mirrors ARCHIVE_VISIT_SORT_ORDERING's shape exactly: "" (the default) is
# the pre-existing -created_at, -id ordering, listed explicitly so
# .get(sort, ARCHIVE_PERSONAL_SORT_ORDERING[""]) has a single source for the
# default instead of a duplicated literal.
ARCHIVE_PERSONAL_SORT_ORDERING: dict[str, tuple[str, str]] = {
    "": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
}


def user_status_counts(user, *, today=None) -> dict:
    """Return per-status counts for a user's archive statuses.

    Counts use the *derived* status (auto-miss overlay), so a planned event
    whose run has ended counts under 'missed', not 'planned'. Single aggregate
    query. Every canonical status slug is always present, even at zero.
    """
    if today is None:
        today = timezone.localdate()
    rows = (
        UserEventStatus.objects.filter(user=user)
        .with_derived_status(today=today)
        .values("derived_status")
        .annotate(count=Count("id"))
    )
    counts = {row["derived_status"]: row["count"] for row in rows}
    return {slug: counts.get(slug, 0) for slug in ARCHIVE_STATUS_SLUGS}


def list_user_statuses(user, status: str = "", *, q: str = "", sort: str = "", today=None):
    """Return a user's archive statuses, newest first, optionally filtered.

    Filtering and the rows' effective status use the *derived* status overlay,
    so the 놓침 filter includes auto-missed rows and 방문 예정 excludes them.
    The event is selected together to avoid per-row queries during rendering.

    ``q`` narrows results to rows whose event or personal_entry title/location
    matches the search term (case-insensitive contains). The user filter is
    always applied first so no cross-user leakage is possible.

    ``sort`` selects the ordering via ARCHIVE_STATUS_SORT_ORDERING; an unknown
    or empty value falls back to the default -updated_at ordering rather than
    raising or returning an empty result.
    """
    if today is None:
        today = timezone.localdate()
    ordering = ARCHIVE_STATUS_SORT_ORDERING.get(sort, "-updated_at")
    # OR (not AND): a status row's subject is exactly one of event/personal_entry
    # (the other is always NULL) — mirrors list_user_unrecorded_visited_statuses'
    # same_subject Exists filter above, which hit the same NULL=NULL trap with AND.
    # Ordering matches list_user_visit_records' canonical -visited_on, -id so the
    # "latest visit" picked here is the same row that list would surface first.
    latest_visit = VisitRecord.objects.filter(
        Q(event=OuterRef("event")) | Q(personal_entry=OuterRef("personal_entry")),
        user=OuterRef("user"),
    ).order_by("-visited_on", "-id")
    queryset = (
        UserEventStatus.objects.filter(user=user)
        .with_derived_status(today=today)
        .select_related("event", "personal_entry")
        .annotate(
            visit_record_id=Subquery(latest_visit.values("id")[:1]),
            review_text=Subquery(latest_visit.values("short_review")[:1]),
        )
        .order_by(ordering)
    )
    if status:
        queryset = queryset.filter(derived_status=status)
    if q:
        queryset = queryset.filter(
            Q(event__title__icontains=q)
            | Q(event__location_name__icontains=q)
            | Q(personal_entry__title__icontains=q)
            | Q(personal_entry__location_name__icontains=q)
        )
    return queryset


def list_user_unrecorded_visited_statuses(user):
    """Return a user's visited status rows whose subject has no visit record
    yet — the collection-first home's "미완성 기록" surface.

    Uses the raw stored status (not with_derived_status) since visited is
    never a derived overlay value. The Exists subquery must OR the event and
    personal_entry matches, not AND them: a status row's subject is exactly
    one of the two (the other is always NULL), so ANDing would compare
    OuterRef("event") or OuterRef("personal_entry") against NULL on every
    row and always evaluate false — silently treating every personal_entry
    subject as permanently unrecorded even after a visit record exists.
    """
    same_subject = VisitRecord.objects.filter(
        Q(event=OuterRef("event")) | Q(personal_entry=OuterRef("personal_entry")),
        user=OuterRef("user"),
    )
    return (
        UserEventStatus.objects.filter(user=user, status=UserEventStatus.Status.VISITED)
        .select_related("event", "personal_entry")
        .annotate(has_record=Exists(same_subject))
        .filter(has_record=False)
        .order_by("-updated_at")
    )


def list_user_interests(user, *, q: str = "", sort: str = ""):
    """Return a user's event interests, with event/personal_entry selected.

    The subject is selected together to avoid per-row queries during rendering.

    ``q`` narrows results to rows whose event or personal_entry title/location
    matches the search term (case-insensitive contains) — mirrors
    list_user_statuses' same OR-across-both-subjects pattern.

    ``sort`` selects the ordering via ARCHIVE_INTEREST_SORT_ORDERING; an
    unknown or empty value falls back to the default -id (최근 찜순) ordering
    rather than raising or returning an empty result.
    """
    queryset = (
        EventInterest.objects.filter(user=user)
        .select_related("event", "personal_entry")
        .order_by(
            ARCHIVE_INTEREST_SORT_ORDERING.get(sort, ARCHIVE_INTEREST_SORT_ORDERING[""])
        )
    )
    if q:
        queryset = queryset.filter(
            Q(event__title__icontains=q)
            | Q(event__location_name__icontains=q)
            | Q(personal_entry__title__icontains=q)
            | Q(personal_entry__location_name__icontains=q)
        )
    return queryset


def user_interest_summary_counts(user, *, today=None) -> dict:
    """Return summary counts for the 찜 목록 page's header cards.

    ``interest_count`` — total 찜 rows (official + unofficial).

    ``ongoing_count`` — official (event-linked) 찜 whose event run is
    currently active, inclusive of both boundary days AND the closing_soon
    window (start_date <= today <= end_date). This matches the row status
    filter shown on screen (events/presenters.derive_event_display's
    ongoing/closing_soon states both render as "진행 중" there), so the
    header number and the row status pills never disagree (§1 D2).

    ``planned_overlap_count`` — official 찜 whose linked event has a
    UserEventStatus row for this user whose *derived* status
    (archive/querysets.with_derived_status) is "planned". Using the derived
    status (not the raw stored value) excludes rows that have auto-derived
    to "missed" (an ended, non-overridden, visit-less planned row) even
    though the stored column still literally says "planned" (§1 D3).

    Both event-scoped counts exclude unofficial (personal_entry-linked) 찜 —
    a PersonalEntry has no run period and is never a status subject target.
    """
    if today is None:
        today = timezone.localdate()

    interest_count = EventInterest.objects.filter(user=user).count()

    ongoing_count = EventInterest.objects.filter(
        user=user,
        event__isnull=False,
        event__start_date__lte=today,
        event__end_date__gte=today,
    ).count()

    planned_event_ids = (
        UserEventStatus.objects.filter(user=user, event__isnull=False)
        .with_derived_status(today=today)
        .filter(derived_status="planned")
        .values_list("event_id", flat=True)
    )
    planned_overlap_count = EventInterest.objects.filter(
        user=user, event__isnull=False, event_id__in=planned_event_ids
    ).count()

    return {
        "interest_count": interest_count,
        "ongoing_count": ongoing_count,
        "planned_overlap_count": planned_overlap_count,
    }


def user_interest_event_ids(user, event_ids=None) -> dict:
    """Return a dict of {event_id: interest_id} for the given user.

    When ``event_ids`` is provided the result is bounded to that id list
    (avoids full-table scans when called from a paginated listing page).
    """
    queryset = EventInterest.objects.filter(user=user)
    if event_ids is not None:
        queryset = queryset.filter(event_id__in=event_ids)
    return {row["event_id"]: row["id"] for row in queryset.values("event_id", "id")}


def user_interest_count(user) -> int:
    """Return the total number of event interests for the given user."""
    return EventInterest.objects.filter(user=user).count()


def list_user_planned_events(user):
    """Return published events the user registered as 방문 예정 (raw planned).

    This is the selectable set when adding a visit record — you record a visit
    for something you planned to go to. Uses the raw 'planned' status (not the
    auto-miss derived overlay) so an event whose run has ended is still
    selectable for a late visit record. Ordered by title.
    """
    return (
        Event.objects.published()
        .filter(
            archive_user_statuses__user=user,
            archive_user_statuses__status=UserEventStatus.Status.PLANNED,
        )
        .order_by("title")
    )


def list_user_upcoming_planned_events(user, *, today=None):
    """Return published events the user planned to attend that haven't
    started yet, soonest first.

    Differs from list_user_planned_events in two ways: filtered to
    start_date strictly after today (a planned event starting today or
    earlier is not "upcoming"), and ordered by start_date (not title) so
    the nearest event leads — this is the collection-first home's "다가오는
    예정 이벤트" surface, not the visit-record selectable set.
    """
    if today is None:
        today = timezone.localdate()
    return (
        Event.objects.published()
        .filter(
            archive_user_statuses__user=user,
            archive_user_statuses__status=UserEventStatus.Status.PLANNED,
            start_date__gt=today,
        )
        .order_by("start_date")
    )


def list_user_personal_entries(user, kind=None, *, q: str = "", sort: str = ""):
    """Return a user's private unofficial items, newest first, optional kind filter.

    ``q`` narrows results to rows whose title, category, location_name,
    work_title, or memo matches the search term (case-insensitive contains).

    ``sort`` selects the ordering via ARCHIVE_PERSONAL_SORT_ORDERING; an
    unknown or empty value falls back to the default -created_at, -id
    ordering rather than raising or returning an empty result.
    """
    queryset = PersonalEntry.objects.filter(user=user).order_by(
        *ARCHIVE_PERSONAL_SORT_ORDERING.get(sort, ARCHIVE_PERSONAL_SORT_ORDERING[""])
    )
    if kind:
        queryset = queryset.filter(kind=kind)
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(category__icontains=q)
            | Q(location_name__icontains=q)
            | Q(work_title__icontains=q)
            | Q(memo__icontains=q)
        )
    return queryset


def user_personal_entry_counts(user) -> dict:
    """Return summary counts for a user's unofficial (personal) entries.

    Used by the archive/personal/ page's summary card and mypage's collection
    count.

    ``visit_linked_count`` is the number of the user's PersonalEntry rows that
    have at least one linked VisitRecord (distinct — a single entry with
    multiple visit records still counts once). An official Event visit never
    touches this count since it filters through the personal_entry FK only.
    """
    queryset = PersonalEntry.objects.filter(user=user)
    return {
        "total_count": queryset.count(),
        "visit_linked_count": queryset.filter(
            archive_user_visit_records__isnull=False
        )
        .distinct()
        .count(),
    }


def user_personal_interest_ids(user) -> dict:
    """Return {personal_entry_id: interest_id} for the user's unofficial 찜.

    Drives the 찜 toggle state on the 비공식 page so each card knows whether it is
    already favourited (and the interest id to delete on un-favourite).
    """
    return {
        row["personal_entry_id"]: row["id"]
        for row in EventInterest.objects.filter(
            user=user,
            personal_entry__isnull=False,
            personal_entry__kind=PersonalEntry.Kind.PLACE,
        ).values("personal_entry_id", "id")
    }


def user_personal_statuses(user) -> dict:
    """Return {personal_entry_id: (status_slug, status_id)} for unofficial 상태.

    Uses the raw stored status — personal entries have no run period, so the
    auto-miss overlay never applies to them.
    """
    return {
        row["personal_entry_id"]: (row["status"], row["id"])
        for row in UserEventStatus.objects.filter(
            user=user,
            personal_entry__isnull=False,
            personal_entry__kind=PersonalEntry.Kind.PLACE,
        ).values("personal_entry_id", "status", "id")
    }


def user_visit_record_counts(user) -> dict:
    """Return summary counts for a user's visit records.

    Always counts the user's FULL visit history (not a filtered subset), so
    the archive/visits/ page's summary cards report a stable total independent
    of any active filter/search. ``memo_count`` is the subset with a non-empty
    short_review.
    """
    queryset = VisitRecord.objects.filter(user=user)
    return {
        "total_count": queryset.count(),
        "memo_count": queryset.exclude(short_review="").count(),
    }


def list_user_visit_records(
    user,
    *,
    official=None,
    category_codes=(),
    category_label: str = "",
    q: str = "",
    sort: str = "",
):
    """Return a user's visit records, newest first, with related data prefetched.

    Shares the canonical ordering and prefetching so the SSR page and the API
    stay consistent (avoids N+1 on event and photos).

    ``official`` — True: only event-linked records; False: only personal-entry
    records; None: no restriction.

    ``category_codes`` / ``category_label`` — when ``category_label`` is truthy
    the queryset is narrowed to rows whose event.category is in category_codes
    OR whose personal_entry.category equals category_label (OR logic). The label
    is checked raw (no lookup) so unofficial entries stored with a free-text
    label match directly.

    ``q`` — case-insensitive contains search across title, location_name (both
    FK sides) and short_review.

    ``sort`` selects the ordering via ARCHIVE_VISIT_SORT_ORDERING; an unknown
    or empty value falls back to the default -visited_on, -id ordering rather
    than raising or returning an empty result.
    """
    queryset = (
        VisitRecord.objects.filter(user=user)
        .select_related("event", "personal_entry")
        .prefetch_related("photos")
        .order_by(*ARCHIVE_VISIT_SORT_ORDERING.get(sort, ARCHIVE_VISIT_SORT_ORDERING[""]))
    )
    if official is True:
        queryset = queryset.filter(event__isnull=False)
    elif official is False:
        queryset = queryset.filter(event__isnull=True)
    if category_label:
        queryset = queryset.filter(
            Q(event__category__in=category_codes)
            | Q(personal_entry__category=category_label)
        )
    if q:
        queryset = queryset.filter(
            Q(event__title__icontains=q)
            | Q(event__location_name__icontains=q)
            | Q(personal_entry__title__icontains=q)
            | Q(personal_entry__location_name__icontains=q)
            | Q(short_review__icontains=q)
        )
    return queryset


def list_user_collection_items(
    user,
    *,
    work_title: str = "",
    character_name: str = "",
    item_type: str = "",
    is_wanted=None,
    duplicate=None,
    tradeable=None,
    owned=None,
    q: str = "",
):
    """Return a user's collection items, newest first, owner-scoped, with
    optional filters (collection domain design plan §4 PR-C5 CP16~22).

    `work_title`/`character_name`/`item_type` are exact-match category
    filters. `duplicate`, `tradeable`, and `owned` are *derived* filters, not
    stored fields — "duplicate" means quantity >= 2, "tradeable" means
    tradeable_quantity > 0, and "owned" means quantity > 0 (the plan
    deliberately removed a separate duplicate_count field, §3-1).

    ``q`` narrows results to rows whose name, work_title, character_name, or
    memo matches the search term (case-insensitive contains), mirroring
    list_user_personal_entries' q pattern. item_type is deliberately not a
    q target field.
    """
    queryset = CollectionItem.objects.filter(user=user).order_by("-id")
    if work_title:
        queryset = queryset.filter(work_title=work_title)
    if character_name:
        queryset = queryset.filter(character_name=character_name)
    if item_type:
        queryset = queryset.filter(item_type=item_type)
    if is_wanted is not None:
        queryset = queryset.filter(is_wanted=is_wanted)
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(work_title__icontains=q)
            | Q(character_name__icontains=q)
            | Q(memo__icontains=q)
        )
    if duplicate is not None:
        if duplicate:
            queryset = queryset.filter(quantity__gte=2)
        else:
            queryset = queryset.filter(quantity__lt=2)
    if tradeable is not None:
        if tradeable:
            queryset = queryset.filter(tradeable_quantity__gt=0)
        else:
            queryset = queryset.filter(tradeable_quantity=0)
    if owned is not None:
        if owned:
            queryset = queryset.filter(quantity__gt=0)
        else:
            queryset = queryset.filter(quantity=0)
    return queryset


def user_collection_item_filter_values(user) -> dict:
    """Return the distinct work_title/character_name/item_type values used by
    a user's collection items, for populating filter widget options.

    Unlike user_visit_category_values (below) — whose caller dedupes only
    after resolving core.vocab labels, keeping this module free of a
    core.vocab import — work_title/character_name/item_type are stored as
    free text with no vocab resolution step, so dedup and blank exclusion are
    done directly here in the query layer rather than deferred to the view.

    Each list is explicitly ordered — the caller renders these directly as
    <select> options, and DISTINCT without ORDER BY has undefined row order
    (e.g. the planner may choose a HashAggregate plan instead of an
    index-derived Sort).
    """
    fields = ("work_title", "character_name", "item_type")
    return {
        field: list(
            CollectionItem.objects.filter(user=user)
            .exclude(**{field: ""})
            .values_list(field, flat=True)
            .distinct()
            .order_by(field)
        )
        for field in fields
    }


def user_collection_item_summary_counts(user) -> dict:
    """Return summary counts for a user's collection items (the /collection/
    summary cards).

    owned, wanted, and tradeable are THREE INDEPENDENT axes, not a
    partition — collection domain design plan §D1
    (.docs/plans/2026-07-15-collection-domain-design-plan.md:55, "wanted와
    보유 공존 허용") approves a row being owned and wanted at once (e.g. a
    duplicate someone still wants more of), and tradeable_quantity > 0 can
    combine with either. A single row can be counted in more than one of
    owned_count / wanted_count / tradeable_count at the same time, so their
    sum is NOT the user's full item count — do not add them together as a
    total. total_count exists precisely because that sum is unreliable: it
    counts every row the user owns regardless of axis membership (a row can
    be off all three axes, e.g. quantity=0/is_wanted=False/
    tradeable_quantity=0, and still be a registered item), so it is the only
    reliable "does this user have any collection items at all" figure.

    - owned_count: quantity > 0 rows (physically held), regardless of
      is_wanted or tradeable_quantity.
    - wanted_count: is_wanted = True rows, regardless of quantity or
      tradeable_quantity.
    - tradeable_count: tradeable_quantity > 0 rows, regardless of quantity or
      is_wanted.
    - total_count: every row belonging to the user, independent of all three
      axes.
    """
    queryset = CollectionItem.objects.filter(user=user)
    return {
        "owned_count": queryset.filter(quantity__gt=0).count(),
        "wanted_count": queryset.filter(is_wanted=True).count(),
        "tradeable_count": queryset.filter(tradeable_quantity__gt=0).count(),
        "total_count": queryset.count(),
    }


def user_collection_item_work_title_facets(user) -> list:
    """Return {"work_title", "count", "first_id"} facets for a user's
    collection items, excluding blank work_title, owner-scoped.

    Sorted by count descending, then work_title ascending as a tie-break —
    same reasoning as user_collection_item_filter_values' explicit
    .order_by(): GROUP BY without ORDER BY has undefined row order (the
    planner may choose a HashAggregate plan instead of an index-derived
    Sort), so the tie-break must be requested explicitly rather than relied
    on implicitly.

    first_id is the id of the work_title's earliest-registered item
    (Min("id")). The caller uses it to re-sort facets into REGISTRATION
    order and derive a per-series color palette from that order — display
    order (count descending) and palette order (first-registered) are
    deliberately different. Assigning colors by count order would make an
    existing work_title's color shift every time any item is added, since
    adding one item can change the count ranking; assigning by
    first-registration order keeps a work_title's color stable for its
    whole lifetime.
    """
    return list(
        CollectionItem.objects.filter(user=user)
        .exclude(work_title="")
        .values("work_title")
        .annotate(count=Count("id"), first_id=Min("id"))
        .order_by("-count", "work_title")
        .values("work_title", "count", "first_id")
    )


def list_items_acquired_at_visit(visit):
    """Return the CollectionItems linked to one VisitRecord, in registration
    order — the visit-record detail page's "이 방문에서 얻은 굿즈" section.

    Uses the reverse FK (CollectionItem.visit_record), so this is an
    intra-archive query with no new cross-domain coupling.
    """
    return list(visit.archive_collection_items.all().order_by("id"))


def list_visit_records_for_personal_entry(entry):
    """Return the VisitRecords attached to one PersonalEntry, newest first —
    the personal-place detail page's "이 장소의 방문 기록" section.

    A dedicated function rather than an extra list_user_visit_records
    argument: that function already has two consumers, and adding a
    parameter for a single detail page would affect both. No `user` filter
    is applied here (matches list_items_acquired_at_visit's precedent) —
    the caller's get_object_or_404(..., user=request.user) already scopes
    `entry` to its owner, and no write path can attach another user's visit
    to it.
    """
    return list(entry.archive_user_visit_records.all().order_by("-visited_on", "-id"))


def user_visit_category_values(user):
    """Return (event__category, personal_entry__category) pairs for a user's visits.

    Ordered newest-first to match the visit timeline. The view uses these pairs
    to derive the full set of category chips without loading full model instances
    or limiting to the current page.
    """
    return (
        VisitRecord.objects.filter(user=user)
        .order_by("-visited_on", "-id")
        .values_list("event__category", "personal_entry__category")
    )


# ---------------------------------------------------------------------------
# Personal activity calendar month query (dual-calendar plan §단계 3,
# CAL-3-03~11). Combines 5 read sources into one flat list of calendar items,
# always scoped to the given user first:
#
#   schedule ("일정")       — planned UserEventStatus rows, the linked
#                             event's full run (start..end, inclusive)
#   visit ("방문")           — VisitRecord.visited_on
#   goods_acquired ("굿즈")  — CollectionItem.acquired_on, falling back to
#                             created_at's local date when unset
#   <ActivityLogEntry.Kind> — the append-only action trail, dated by
#                             occurred_at's local date
#   <ActivityLogEntry.Kind.INTEREST_ADDED> fallback — a still-existing
#                             EventInterest with no matching log row (legacy
#                             pre-launch 찜, §7.5 "no backfill" — the fallback
#                             is only used when no log row already covers it,
#                             so the two never double-count the same 찜)
#
# Each source is a single query; date-derivation and month-window filtering
# for the two "fact date with a fallback" sources (goods, 찜) happens in
# Python since the fallback can't be expressed as one simple field lookup —
# acceptable at today's per-user row counts (no aggregation table, service
# design §14).
# ---------------------------------------------------------------------------

SCHEDULE_KIND = "schedule"
VISIT_KIND = "visit"
GOODS_ACQUIRED_KIND = "goods_acquired"


@dataclass(frozen=True)
class CalendarActivityItem:
    """One calendar-displayable activity row (dual-calendar service design
    §7.3). A single-fact-date item (방문/굿즈 획득/행동성 활동) sets `date`
    and leaves `start`/`end` None; a period item (일정) sets `start`/`end`
    (inclusive) and leaves `date` None.

    `label`/`url`/`time_text` (additive — web-layer display fields, not new
    business rules; each private helper below fills them from the exact
    object it already holds at construction time):
    - `label`: the subject's display name (event title / CollectionItem.name
      / ActivityLogEntry.subject_label — the durable snapshot that survives
      the source row's own deletion).
    - `url`: the linked edit/detail screen (event detail, visit-record edit,
      collection-item edit), or `None` when the underlying row is a
      SET_NULL ActivityLogEntry whose target has since been deleted (only
      `subject_label` survives that case — there is nothing left to link
      to).
    - `time_text`: localtime "HH:MM" for action-time items sourced from
      ActivityLogEntry.occurred_at only (§7.3-3 "행동성 활동"); every other
      source has no time-of-day to show (VisitRecord.visited_on and
      CollectionItem's date fields are plain dates, and a period item is a
      date range) and leaves this "".
    """

    kind: str
    date: _date | None = None
    start: _date | None = None
    end: _date | None = None
    label: str = ""
    url: str | None = None
    time_text: str = ""


def _calendar_month_bounds(year, month):
    month_start = _date(year, month, 1)
    month_end = _date(year, month, calendar.monthrange(year, month)[1])
    return month_start, month_end


def _schedule_items(user, month_start, month_end):
    """Planned-status rows whose linked event run overlaps the month —
    mirrors events.querysets.EventQuerySet.overlapping_month's boundary rule,
    applied through the event FK instead of Event.objects directly."""
    statuses = (
        UserEventStatus.objects.filter(
            user=user,
            status=UserEventStatus.Status.PLANNED,
            event__isnull=False,
            event__start_date__isnull=False,
            event__start_date__lte=month_end,
        )
        .filter(
            Q(event__end_date__isnull=True, event__start_date__gte=month_start)
            | Q(event__end_date__isnull=False, event__end_date__gte=month_start)
        )
        .select_related("event")
    )
    return [
        CalendarActivityItem(
            kind=SCHEDULE_KIND,
            start=status.event.start_date,
            end=status.event.end_date or status.event.start_date,
            label=status.event.title,
            url=reverse("event-detail-page", args=[status.event_id]),
        )
        for status in statuses
    ]


def _visit_items(user, month_start, month_end):
    visits = VisitRecord.objects.filter(
        user=user, visited_on__gte=month_start, visited_on__lte=month_end
    ).select_related("event", "personal_entry")
    return [
        CalendarActivityItem(
            kind=VISIT_KIND,
            date=visit.visited_on,
            label=visit.event.title if visit.event_id else visit.personal_entry.title,
            url=reverse("archive-visit-edit-page", args=[visit.id]),
        )
        for visit in visits
    ]


def _goods_acquired_items(user, month_start, month_end):
    items = []
    for item in CollectionItem.objects.filter(user=user):
        display_date = item.acquired_on or timezone.localdate(item.created_at)
        if month_start <= display_date <= month_end:
            items.append(
                CalendarActivityItem(
                    kind=GOODS_ACQUIRED_KIND,
                    date=display_date,
                    label=item.name,
                    url=reverse("collection-edit-page", args=[item.id]),
                )
            )
    return items


def _log_entry_items(user, month_start, month_end):
    """ActivityLogEntry rows carry a durable `subject_label` snapshot
    precisely so this source still has a label after its target row is
    gone (event/visit_record/collection_item are all SET_NULL on the
    target's own deletion, archive/models.py) — `url` degrades to `None`
    in that case since there is nothing left to link to."""
    entries = ActivityLogEntry.objects.filter(
        user=user,
        occurred_at__date__gte=month_start,
        occurred_at__date__lte=month_end,
    )
    items = []
    for entry in entries:
        if entry.event_id:
            url = reverse("event-detail-page", args=[entry.event_id])
        elif entry.visit_record_id:
            url = reverse("archive-visit-edit-page", args=[entry.visit_record_id])
        elif entry.collection_item_id:
            url = reverse("collection-edit-page", args=[entry.collection_item_id])
        else:
            url = None
        # timezone.localdate(entry.occurred_at) == timezone.localtime(entry.occurred_at).date()
        # for an aware datetime (USE_TZ=True here) — same displayed date as
        # before this field addition, just derived from the same localtime
        # value that also yields time_text, so CAL-3's (kind, date)
        # observations are unchanged.
        local_dt = timezone.localtime(entry.occurred_at)
        items.append(
            CalendarActivityItem(
                kind=entry.kind,
                date=local_dt.date(),
                label=entry.subject_label,
                url=url,
                time_text=local_dt.strftime("%H:%M"),
            )
        )
    return items


def _interest_added_fallback_items(user, month_start, month_end):
    """§7.5 no-backfill fallback: a still-existing EventInterest with no
    matching interest_added log row (legacy data from before ActivityLogEntry
    existed). Excludes any event already covered by a real log row so a
    post-launch 찜 is never counted twice."""
    logged_event_ids = set(
        ActivityLogEntry.objects.filter(
            user=user,
            kind=ActivityLogEntry.Kind.INTEREST_ADDED,
            event__isnull=False,
        ).values_list("event_id", flat=True)
    )
    interests = EventInterest.objects.filter(user=user, event__isnull=False).exclude(
        event_id__in=logged_event_ids
    ).select_related("event")
    items = []
    for interest in interests:
        display_date = timezone.localdate(interest.created_at)
        if month_start <= display_date <= month_end:
            items.append(
                CalendarActivityItem(
                    kind=ActivityLogEntry.Kind.INTEREST_ADDED,
                    date=display_date,
                    label=interest.event.title,
                    url=reverse("event-detail-page", args=[interest.event_id]),
                )
            )
    return items


def list_user_activity_for_month(user, *, year, month, kinds=None):
    """Return the user's calendar-displayable activity for one month as a
    flat list of CalendarActivityItem, always scoped to `user` first.

    `kinds`, when given, narrows the result to that subset of kind strings
    (SCHEDULE_KIND, VISIT_KIND, GOODS_ACQUIRED_KIND, or an
    ActivityLogEntry.Kind value).
    """
    month_start, month_end = _calendar_month_bounds(year, month)

    items = (
        _schedule_items(user, month_start, month_end)
        + _visit_items(user, month_start, month_end)
        + _goods_acquired_items(user, month_start, month_end)
        + _log_entry_items(user, month_start, month_end)
        + _interest_added_fallback_items(user, month_start, month_end)
    )

    if kinds is not None:
        allowed = set(kinds)
        items = [item for item in items if item.kind in allowed]

    return items


def _latest_schedule_match_date(user, q, kinds):
    """Latest .start among PLANNED statuses whose event title matches `q` —
    mirrors _schedule_items' (kind, label, date) rules but filters by title
    in the DB instead of building every row and comparing in Python."""
    if kinds is not None and SCHEDULE_KIND not in kinds:
        return None
    return UserEventStatus.objects.filter(
        user=user,
        status=UserEventStatus.Status.PLANNED,
        event__isnull=False,
        event__title__icontains=q,
    ).aggregate(latest=Max("event__start_date"))["latest"]


def _latest_visit_match_date(user, q, kinds):
    """Latest visited_on among visits whose event or personal_entry title
    matches `q` — mirrors _visit_items' label sourcing (event title if
    linked, else personal_entry title)."""
    if kinds is not None and VISIT_KIND not in kinds:
        return None
    return (
        VisitRecord.objects.filter(user=user)
        .filter(Q(event__title__icontains=q) | Q(personal_entry__title__icontains=q))
        .aggregate(latest=Max("visited_on"))["latest"]
    )


def _latest_goods_match_date(user, q, kinds):
    """Latest derived display date (acquired_on or created_at's local date)
    among CollectionItems whose name matches `q`. The display date is a
    derived value, not a plain column, so it cannot be aggregated in the DB —
    but the row set itself is already narrowed by name__icontains, so only
    the small set of actual matches (not the user's whole collection) is
    pulled into Python to pick the max."""
    if kinds is not None and GOODS_ACQUIRED_KIND not in kinds:
        return None
    match_dates = [
        item.acquired_on or timezone.localdate(item.created_at)
        for item in CollectionItem.objects.filter(user=user, name__icontains=q)
    ]
    return max(match_dates) if match_dates else None


def _latest_log_entry_match_date(user, q, kinds):
    """Latest local display date among ActivityLogEntry rows whose
    subject_label matches `q`, optionally narrowed to `kinds` first (a
    kind__in filter in the DB, same effect as list_user_activity_for_month's
    Python-side kind filter). occurred_at -> local date is a derived value
    (timezone.localtime(...).date(), same as _log_entry_items), so it is
    computed in Python only over the already-matched rows."""
    entries = ActivityLogEntry.objects.filter(user=user, subject_label__icontains=q)
    if kinds is not None:
        entries = entries.filter(kind__in=kinds)
    match_dates = [
        timezone.localtime(occurred_at).date()
        for occurred_at in entries.values_list("occurred_at", flat=True)
    ]
    return max(match_dates) if match_dates else None


def _latest_interest_fallback_match_date(user, q, kinds):
    """Latest derived display date (created_at's local date) among the §7.5
    no-backfill fallback's still-existing EventInterests whose event title
    matches `q`, excluding any event already covered by a real
    interest_added log row — mirrors _interest_added_fallback_items exactly,
    just narrowed by title in the DB first."""
    if kinds is not None and ActivityLogEntry.Kind.INTEREST_ADDED not in kinds:
        return None
    logged_event_ids = set(
        ActivityLogEntry.objects.filter(
            user=user,
            kind=ActivityLogEntry.Kind.INTEREST_ADDED,
            event__isnull=False,
        ).values_list("event_id", flat=True)
    )
    created_ats = (
        EventInterest.objects.filter(user=user, event__isnull=False, event__title__icontains=q)
        .exclude(event_id__in=logged_event_ids)
        .values_list("created_at", flat=True)
    )
    match_dates = [timezone.localdate(created_at) for created_at in created_ats]
    return max(match_dates) if match_dates else None


def find_latest_activity_date_for_query(user, q, *, kinds=None):
    """Return the most recent calendar date where one of `user`'s activity
    items' label contains `q` (case-insensitive), or None with no match —
    the read side of the activity calendar's date-jump search (dual-calendar
    editorial plan §4-a-1). Blank/whitespace-only `q` always returns None
    without querying.

    Unlike list_user_activity_for_month (bounded to one month, so its
    per-source Python loops stay small), this function's date range is
    unbounded — the whole activity history — so the `q`-vs-label comparison
    is pushed into each source's own DB query (name/title/subject_label
    __icontains=q) instead of building every row across the user's entire
    history and filtering in Python. Each per-source helper above mirrors
    the exact (kind, label, date) rules its list_user_activity_for_month
    counterpart uses, just narrowed by `q` (and `kinds`) in the DB first.

    This function's only caller (core.views.activity_calendar) passes it the
    currently active type= filter's kinds, so a jump never lands on a date
    whose only match is a kind currently hidden from view.

    A period item (schedule) is matched by its whole displayed range, but
    the date returned for it is `.start` — the first day the month grid
    would actually show it (mirrors list_user_activity_for_month's own
    day-by-day bucketing of period items).
    """
    q = q.strip()
    if not q:
        return None

    match_dates = [
        match_date
        for match_date in (
            _latest_schedule_match_date(user, q, kinds),
            _latest_visit_match_date(user, q, kinds),
            _latest_goods_match_date(user, q, kinds),
            _latest_log_entry_match_date(user, q, kinds),
            _latest_interest_fallback_match_date(user, q, kinds),
        )
        if match_date is not None
    ]
    return max(match_dates) if match_dates else None
