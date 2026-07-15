"""Read layer for the archive domain.

Reusable query logic for user event statuses, event interests, and visit records.
Query/aggregate logic lives here, not in the view layer — mirrors
drafts/queries.py.
"""
from django.db.models import Count, Q
from django.utils import timezone

from events.models import Event

from .models import CollectionItem, EventInterest, PersonalEntry, UserEventStatus, VisitRecord

# Canonical archive status slugs, sourced from the model's own choices so the
# set has a single source of truth. Excludes "interested" (now EventInterest).
ARCHIVE_STATUS_SLUGS: tuple[str, ...] = tuple(UserEventStatus.Status.values)

# Page sizes for the archive SSR list pages (rendered by core.views). Kept here
# beside the list queries they bound, mirroring events.queries.PUBLIC_LISTING_PAGE_SIZE.
ARCHIVE_RECORD_PAGE_SIZE = 10  # 기록장 (/archive/) — 저장한 행사
ARCHIVE_STATUS_PAGE_SIZE = 5  # 예정 목록 (/archive/statuses/)
ARCHIVE_VISIT_PAGE_SIZE = 5  # 방문 기록 (/archive/visits/)
ARCHIVE_PERSONAL_PAGE_SIZE = 5  # 비공식 목록 (/archive/items/)


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


def list_user_statuses(user, status: str = "", *, q: str = "", today=None):
    """Return a user's archive statuses, newest first, optionally filtered.

    Filtering and the rows' effective status use the *derived* status overlay,
    so the 놓침 filter includes auto-missed rows and 방문 예정 excludes them.
    The event is selected together to avoid per-row queries during rendering.

    ``q`` narrows results to rows whose event or personal_entry title/location
    matches the search term (case-insensitive contains). The user filter is
    always applied first so no cross-user leakage is possible.
    """
    if today is None:
        today = timezone.localdate()
    queryset = (
        UserEventStatus.objects.filter(user=user)
        .with_derived_status(today=today)
        .select_related("event", "personal_entry")
        .order_by("-updated_at")
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


def list_user_interests(user):
    """Return a user's event interests, newest first, with event selected.

    The event is selected together to avoid per-row queries during rendering.
    """
    return (
        EventInterest.objects.filter(user=user)
        .select_related("event", "personal_entry")
        .order_by("-id")
    )


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


def list_user_personal_entries(user, kind=None, *, q: str = ""):
    """Return a user's private unofficial items, newest first, optional kind filter.

    ``q`` narrows results to rows whose title, category, location_name,
    work_title, or memo matches the search term (case-insensitive contains).
    """
    queryset = PersonalEntry.objects.filter(user=user).order_by("-created_at", "-id")
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

    Mirrors user_visit_record_counts' dict shape. Used by the archive/items/
    page's summary cards: ``goods_count`` is a simple ``total_count -
    place_count`` arithmetic derivation done by the caller (not a DB
    aggregate), so it stays out of this dict.
    """
    queryset = PersonalEntry.objects.filter(user=user)
    return {
        "total_count": queryset.count(),
        "place_count": queryset.filter(kind=PersonalEntry.Kind.PLACE).count(),
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
    """
    queryset = (
        VisitRecord.objects.filter(user=user)
        .select_related("event", "personal_entry")
        .prefetch_related("photos")
        .order_by("-visited_on", "-id")
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


def list_user_collection_items(user):
    """Return a user's collection items, newest first, owner-scoped.

    Mirrors list_user_personal_entries' owner-scoped ordering shape.
    """
    return CollectionItem.objects.filter(user=user).order_by("-id")


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
