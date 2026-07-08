from django.conf import settings
from django.db import models


class StaffActionLog(models.Model):
    """Append-only audit trail for staff actions.

    Minimal v1 scope: no before/after snapshot, no polymorphic target —
    records draft approve/reject actions as well as home-category config
    changes (which have no target draft). Read access is restricted to
    superusers (see `staff/admin.py`); operators (is_staff) can only see the
    dashboard's `recent_actions` summary (actor/action/target/time, no ip/ua).
    """

    class Action(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        HOME_CATEGORIES = "home_categories", "Home categories"
        EVENT_UPDATE = "event_update", "Event update"
        EVENT_CREATE = "event_create", "Event create"
        EVENT_UNPUBLISH = "event_unpublish", "Event unpublish"
        EVENT_REPUBLISH = "event_republish", "Event republish"
        EVENT_DELETE = "event_delete", "Event delete"
        DRAFT_DISCOVER = "draft_discover", "Draft discover"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    target_draft = models.ForeignKey(
        "drafts.EventDraft",
        null=True,
        on_delete=models.SET_NULL,
    )
    target_event = models.ForeignKey(
        "events.Event",
        null=True,
        on_delete=models.SET_NULL,
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        target_id = self.target_draft_id if self.target_draft_id is not None else self.target_event_id
        if target_id is None:
            return f"{self.action} by {self.actor_id}"
        return f"{self.action} #{target_id} by {self.actor_id}"
