"""Shared helpers for staff/views/ submodules.

Only value-preparation logic lives here — the `StaffActionLog.objects.create()`
call itself stays in each caller's own `transaction.atomic()` block (a log
write failure must roll back the action it is auditing, so the create() call
cannot be hidden behind an indirection that obscures that invariant).
"""


def _staff_action_metadata(request):
    """Extract actor/ip/user-agent for a StaffActionLog entry from the request."""
    return {
        "actor": request.user,
        "ip_address": request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
    }


def _action_log_kwargs(metadata, action, *, target_draft=None, target_event=None):
    """Assemble StaffActionLog.objects.create() kwargs from `metadata` + `action`.

    `metadata` is a dict from `_staff_action_metadata(request)`. Taking the
    already-extracted dict (instead of `request` itself) lets callers that
    already compute `metadata` once per request/loop reuse it without a
    second extraction — e.g. StaffDraftBulkApproveView._approve_one, a
    per-item static helper that only receives `metadata`, not `request`.

    Usage: ``StaffActionLog.objects.create(**_action_log_kwargs(metadata,
    StaffActionLog.Action.APPROVE, target_draft=draft))`` inside the
    caller's own transaction.atomic() block.

    StaffActionLog has no generic metadata field (only target_draft and
    target_event) — every call site passes at most one of the two target_*
    kwargs, the other stays at its None default.
    """
    return {
        "action": action,
        "target_draft": target_draft,
        "target_event": target_event,
        **metadata,
    }
