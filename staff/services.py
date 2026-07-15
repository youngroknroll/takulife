"""Staff-only orchestration that spans multiple domain apps.

events/services.py must never import archive (architecture boundary, see
tests/test_architecture_boundaries.py) — but the "is this event safe to
hard-delete?" question needs to read archive's 3 Event-referencing models
(EventInterest/UserEventStatus/VisitRecord, all on_delete=CASCADE from Event).
staff is the presentation/orchestration layer allowed to depend on both
events and archive, so that guard lives here instead of in events/services.py.
"""
from events.services import hard_delete_event


class EventHasArchiveReferencesError(Exception):
    """Raised when delete_event is asked to remove an event that still has
    archive references (EventInterest/UserEventStatus/VisitRecord/
    CollectionItem). Interest/status/visit are CASCADE, so a hard delete
    would silently wipe users' personal archive data; CollectionItem is
    SET_NULL (survives), but the reference is still surfaced here so staff
    can make an informed call before detaching a user's collection from its
    event. Carries the per-kind counts so callers can show them.
    """

    def __init__(self, *, interest_count, status_count, visit_count, collection_item_count):
        self.interest_count = interest_count
        self.status_count = status_count
        self.visit_count = visit_count
        self.collection_item_count = collection_item_count
        super().__init__(
            "Event has archive references: "
            f"interest={interest_count}, status={status_count}, visit={visit_count}, "
            f"collection_item={collection_item_count}"
        )


def event_archive_reference_counts(*, event):
    """Return {"interest": N, "status": N, "visit": N, "collection_item": N} for `event`.

    Reads the 4 reverse relations from archive/models.py (EventInterest.event,
    UserEventStatus.event, VisitRecord.event, CollectionItem.event).
    """
    return {
        "interest": event.archive_user_interests.count(),
        "status": event.archive_user_statuses.count(),
        "visit": event.archive_user_visit_records.count(),
        "collection_item": event.archive_collection_items.count(),
    }


def delete_event(*, event):
    """Hard-delete `event` only if it has zero archive references.

    Raises EventHasArchiveReferencesError (with counts) instead of deleting
    when any of the 4 archive models still reference this event — deleting
    it would CASCADE-wipe those users' interests/statuses/visit records (and
    detach their collection items' event link, even though those rows
    survive via SET_NULL).
    """
    counts = event_archive_reference_counts(event=event)
    if sum(counts.values()) > 0:
        raise EventHasArchiveReferencesError(
            interest_count=counts["interest"],
            status_count=counts["status"],
            visit_count=counts["visit"],
            collection_item_count=counts["collection_item"],
        )
    hard_delete_event(event=event)
