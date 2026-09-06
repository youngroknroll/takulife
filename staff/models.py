from django.conf import settings
from django.db import models


class StaffActionLog(models.Model):
    """스태프 행동을 기록하는 추가 전용 감사 로그.

    변경 전/후 스냅샷은 남기지 않는다. 전체 조회는 슈퍼유저만 가능하고
    (`staff/admin.py`), 운영자(is_staff)는 대시보드 요약(행위자/행동/대상/
    시각만, ip·user-agent 제외)만 볼 수 있다.
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
        EVENT_VERIFY = "event_verify", "Event verify"
        DRAFT_DISCOVER = "draft_discover", "Draft discover"
        SOURCE_DISCOVER = "source_discover", "Source discover"
        STAFF_GRANT = "staff_grant", "Staff grant"
        STAFF_REVOKE = "staff_revoke", "Staff revoke"
        USER_DEACTIVATE = "user_deactivate", "User deactivate"
        USER_REACTIVATE = "user_reactivate", "User reactivate"

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
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.target_draft_id is not None:
            target_id = self.target_draft_id
        elif self.target_event_id is not None:
            target_id = self.target_event_id
        else:
            target_id = self.target_user_id
        if target_id is None:
            return f"{self.action} by {self.actor_id}"
        return f"{self.action} #{target_id} by {self.actor_id}"
