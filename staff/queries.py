"""Public read layer for the staff console dashboard.

Provides reusable read logic for staff-facing summaries. Business logic
lives here, not in the view layer (mirrors drafts/queries.py, events/queries.py).
"""
from .models import StaffActionLog


def recent_staff_actions(limit=10):
    """Return the most recent StaffActionLog rows, newest first, limited.

    select_related("actor", "target_draft") avoids N+1 queries when the
    dashboard template reads actor email / draft title for each row.

    Returns full StaffActionLog objects (not a dict projection): this is a
    staff-internal read, so exposing the full model here is safe. The
    dashboard template itself only renders actor/action/target_draft/
    created_at and must not render ip_address/user_agent (those stay
    superuser-only, surfaced only via staff/admin.py).
    """
    return list(
        StaffActionLog.objects.select_related("actor", "target_draft").all()[:limit]
    )
