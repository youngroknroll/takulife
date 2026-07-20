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
