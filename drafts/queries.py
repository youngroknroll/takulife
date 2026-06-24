"""Public read layer for event drafts.

Provides reusable aggregate query logic for the drafts domain.
Business logic lives here, not in the view layer.
"""
from django.db.models import Count

from .models import EventDraft

_ALL_STATUSES = (
    EventDraft.ReviewStatus.PENDING,
    EventDraft.ReviewStatus.APPROVED,
    EventDraft.ReviewStatus.REJECTED,
)


def draft_review_stats() -> dict:
    """Return review status counts as a dict with keys pending/approved/rejected.

    Uses a single aggregate query. All three keys are always present,
    even when a given status has zero records.
    """
    rows = (
        EventDraft.objects.values("review_status")
        .annotate(count=Count("id"))
    )
    counts = {row["review_status"]: row["count"] for row in rows}
    return {status: counts.get(status, 0) for status in _ALL_STATUSES}
