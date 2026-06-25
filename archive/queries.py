"""Read layer for the archive domain.

Reusable query logic for user event statuses and visit records.
Query/aggregate logic lives here, not in the view layer — mirrors
drafts/queries.py.
"""
from django.db.models import Count

from .models import UserEventStatus, VisitRecord

# Canonical archive status slugs, sourced from the model's own choices so the
# set has a single source of truth.
ARCHIVE_STATUS_SLUGS: tuple[str, ...] = tuple(UserEventStatus.Status.values)


def user_status_counts(user) -> dict:
    """Return per-status counts for a user's archive statuses.

    Uses a single aggregate query. Every canonical status slug is always
    present, even when a given status has zero records.
    """
    rows = (
        UserEventStatus.objects.filter(user=user)
        .values("status")
        .annotate(count=Count("id"))
    )
    counts = {row["status"]: row["count"] for row in rows}
    return {slug: counts.get(slug, 0) for slug in ARCHIVE_STATUS_SLUGS}


def list_user_statuses(user, status: str = ""):
    """Return a user's archive statuses, newest first, optionally filtered.

    The event is selected together to avoid per-row queries during rendering.
    """
    queryset = (
        UserEventStatus.objects.filter(user=user)
        .select_related("event")
        .order_by("-updated_at")
    )
    if status:
        queryset = queryset.filter(status=status)
    return queryset


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
