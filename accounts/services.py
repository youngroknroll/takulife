"""Account deletion state machine (10-day grace period).

See .docs/plans/2026-07-20-deletion-grace-period-plan.md. No code path other
than accounts.management.commands.purge_deleted_accounts may call
`User.delete()` for a self-service deletion request — every other entry point
(the delete_account view, and later the login-cancels-deletion signal) only
reads or writes `deletion_requested_at` through the functions below.
"""
import logging
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from .models import User

logger = logging.getLogger(__name__)

# The grace period between a deletion request and eligibility for
# execute_pending_deletions' purge (see
# .docs/plans/2026-07-20-deletion-grace-period-plan.md).
DELETION_GRACE_PERIOD = timedelta(days=10)


def request_deletion(user):
    """Record `user` as pending deletion; the account itself is untouched.

    Every session belonging to `user` is invalidated here, not just the one
    that submitted the request — a panic deletion has to end an attacker's
    (or simply another device's) session too, or that session would keep
    working for the whole 10-day grace period (Security review, see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md).
    """
    user.deletion_requested_at = timezone.now()
    user.save(update_fields=["deletion_requested_at"])
    for session in Session.objects.all():
        if session.get_decoded().get("_auth_user_id") == str(user.pk):
            session.delete()


def cancel_deletion(user):
    """Clear a pending deletion request; return the number of rows updated.

    The conditional `deletion_requested_at__isnull=False` update (rather than
    an unconditional save) makes the rowcount a reliable signal of whether a
    request actually existed and was cleared here — the caller (the
    login-cancels-deletion signal, and later the purge command's concurrency
    guard) can tell a real cancellation apart from a no-op without a second
    query.
    """
    return User.objects.filter(pk=user.pk, deletion_requested_at__isnull=False).update(
        deletion_requested_at=None
    )


def record_password_change(user):
    """Stamp `user.password_changed_at` with now; the sole write path for
    that field. Called from accounts.signals' allauth password-lifecycle
    receivers (password_changed, password_set, password_reset) — never
    written directly from a signal handler (see .docs mypage brief).
    """
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password_changed_at"])


def execute_pending_deletions(now=None):
    """Purge every account whose grace period has fully elapsed.

    Each candidate is re-verified and deleted in its own transaction (never
    the whole batch in one transaction) so one row's outcome cannot block or
    roll back any other row. `select_for_update` re-reads under a lock
    immediately before deleting, so a `cancel_deletion` landing in the gap
    between the initial candidate scan and this transaction is respected
    (DEL-08) instead of being purged anyway. `user.delete()` here is the only
    place a self-service deletion request may hard-delete a row (plan
    invariant — every other path only reads/writes `deletion_requested_at`).

    A single row's failure (e.g. a CASCADE/signal error on one account) is
    isolated to that row and logged, not left to abort the whole sweep —
    this mirrors discover_drafts.py's per-item isolation. Returns a summary
    dict with `deleted` (pks actually removed) and `failed` (`(pk, str(exc))`
    pairs) so the caller (purge_deleted_accounts) can report and, if
    non-empty, raise.
    """
    now = now or timezone.now()
    cutoff = now - DELETION_GRACE_PERIOD
    candidate_pks = list(
        User.objects.filter(deletion_requested_at__lte=cutoff).values_list("pk", flat=True)
    )
    deleted_pks = []
    failed = []
    for pk in candidate_pks:
        try:
            with transaction.atomic():
                user = (
                    User.objects.select_for_update()
                    .filter(pk=pk, deletion_requested_at__lte=cutoff)
                    .first()
                )
                if user is not None:
                    user.delete()
                    deleted_pks.append(pk)
        except Exception as exc:
            # except-ok: isolated per-row so one failure cannot block the rest
            logger.exception("Failed to purge pending-deletion user pk=%s", pk)
            failed.append((pk, str(exc)))
    return {"deleted": deleted_pks, "failed": failed}
