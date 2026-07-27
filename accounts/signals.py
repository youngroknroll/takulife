from allauth.account.signals import password_changed, password_reset, password_set
from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from . import services


@receiver(user_logged_in)
def cancel_pending_deletion_on_login(sender, request, user, **kwargs):
    """A successful login during the 10-day grace period is itself the
    cancellation — it needs no extra confirmation step, because logging in
    already re-authenticates the owner (see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md). Standard Django
    auth signal (not an allauth adapter hook) so this fires for every login
    backend, including the social path.
    """
    cancelled = services.cancel_deletion(user)
    if cancelled and request is not None:
        messages.success(request, "탈퇴 예약이 취소되었습니다.")


@receiver([password_changed, password_set, password_reset])
def _on_password_event(sender, request, user, **kwargs):
    """Records password_changed_at on any of allauth's three
    password-lifecycle signals (see .docs mypage brief). A single receiver
    covers password_changed (change form), password_set (first-time set for
    a social/no-password account), and password_reset (both the email-link
    and code-based reset flows converge on this same allauth signal). Thin
    by design — all writing happens in accounts.services.record_password_change,
    the established write gateway for security-adjacent User fields (see
    request_deletion/cancel_deletion).
    """
    services.record_password_change(user)
