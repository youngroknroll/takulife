"""Read layer for the archive domain.

Reusable query logic for user event statuses, event interests, and visit records.
Query/aggregate logic lives here, not in the view layer — mirrors
drafts/queries.py.
"""
from django.db.models import Count
from django.utils import timezone

from events.models import Event

from .models import EventInterest, UserEventStatus, VisitRecord

# Canonical archive status slugs, sourced from the model's own choices so the
# set has a single source of truth. Excludes "interested" (now EventInterest).
ARCHIVE_STATUS_SLUGS: tuple[str, ...] = tuple(UserEventStatus.Status.values)


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


def list_user_statuses(user, status: str = "", *, today=None):
    """Return a user's archive statuses, newest first, optionally filtered.

    Filtering and the rows' effective status use the *derived* status overlay,
    so the 놓침 filter includes auto-missed rows and 방문 예정 excludes them.
    The event is selected together to avoid per-row queries during rendering.
    """
    if today is None:
        today = timezone.localdate()
    queryset = (
        UserEventStatus.objects.filter(user=user)
        .with_derived_status(today=today)
        .select_related("event")
        .order_by("-updated_at")
    )
    if status:
        queryset = queryset.filter(derived_status=status)
    return queryset


def list_user_interests(user):
    """Return a user's event interests, newest first, with event selected.

    The event is selected together to avoid per-row queries during rendering.
    """
    return (
        EventInterest.objects.filter(user=user)
        .select_related("event")
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


def list_user_visit_records(user):
    """Return a user's visit records, newest first, with related data prefetched.

    Shares the canonical ordering and prefetching so the SSR page and the API
    stay consistent (avoids N+1 on event and photos).
    """
    return (
        VisitRecord.objects.filter(user=user)
        .select_related("event")
        .prefetch_related("photos")
        .order_by("-visited_on", "-id")
    )
