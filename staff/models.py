from django.conf import settings
from django.db import models


class StaffActionLog(models.Model):
    """Append-only audit trail for staff review actions.

    Minimal v1 scope: no before/after snapshot, no polymorphic target — only
    draft approve/reject actions are recorded. Read access is restricted to
    superusers (see `staff/admin.py`); operators (is_staff) can only see the
    dashboard's `recent_actions` summary (actor/action/target/time, no ip/ua).
    """

    class Action(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"

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
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} #{self.target_draft_id} by {self.actor_id}"
