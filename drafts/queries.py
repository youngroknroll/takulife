"""Public read layer for event drafts.

Provides reusable aggregate query logic for the drafts domain.
Business logic lives here, not in the view layer.
"""
from django.db.models import Count

from .models import DraftSource, EventDraft

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


DRAFT_LISTING_PAGE_SIZE = 20


def list_drafts(status: str = ""):
    """Return drafts ordered by -id, optionally filtered by review_status.

    status="" (default) returns all. An unknown status yields an empty
    queryset — the view is responsible for normalizing unknown values to "".
    """
    qs = EventDraft.objects.order_by("-id")
    if status:
        qs = qs.filter(review_status=status)
    return qs


def list_draft_sources():
    """Return all DraftSource rows ordered by -enabled, then name.

    Enabled sources surface first (they are the ones actually collecting),
    then alphabetical within each enabled state. Used by the staff dashboard
    freshness panel (prompt_plan.md §3-1-5) — the view calls this helper
    rather than querying DraftSource directly.
    """
    return DraftSource.objects.order_by("-enabled", "name")
