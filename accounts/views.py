import logging
import time

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from . import services

logger = logging.getLogger(__name__)

# Password re-check on this view has no throttle of its own otherwise: axes
# only hooks the login backend, and allauth's ACCOUNT_RATE_LIMITS does not
# cover this custom view, so a hijacked session could brute-force the
# password indefinitely without this counter.
MAX_DELETE_PASSWORD_ATTEMPTS = 5
DELETE_PASSWORD_LOCKOUT_SECONDS = 60 * 15
DELETE_LOCKOUT_MESSAGE = "비밀번호를 여러 번 잘못 입력했습니다. 잠시 후 다시 시도해 주세요."


def _delete_attempts_cache_key(user):
    return f"account-delete-attempts:{user.pk}"


def _is_delete_locked(user):
    """True once `user` has exhausted the failure budget for this window.

    The window's deadline is stored explicitly in the cached record (rather
    than relied on implicitly via the cache entry's own physical TTL): the
    shared cache backend is DatabaseCache (config/settings.py CACHES, PR-0e),
    and unlike LocMemCache.incr(), DatabaseCache has no incr() override —
    BaseCache.incr() falls back to a plain `self.set(key, new_value)` call
    with no timeout argument, which resets the entry's physical TTL to the
    cache's default TIMEOUT on every failed attempt. If the fixed 15-minute
    window were represented only by that physical TTL, each new failure
    would silently shrink and refresh it, turning the intended fixed window
    into an effectively sliding, shorter one. Storing our own deadline and
    comparing it explicitly keeps the window fixed to the first failure
    regardless of what the cache backend does to the physical TTL.
    """
    record = cache.get(_delete_attempts_cache_key(user))
    if not record or record["deadline"] <= time.time():
        return False
    return record["count"] >= MAX_DELETE_PASSWORD_ATTEMPTS


def _register_failed_delete_attempt(user):
    key = _delete_attempts_cache_key(user)
    now = time.time()
    record = cache.get(key)
    if not record or record["deadline"] <= now:
        record = {"count": 0, "deadline": now + DELETE_PASSWORD_LOCKOUT_SECONDS}
    record["count"] += 1
    if record["count"] == MAX_DELETE_PASSWORD_ATTEMPTS:
        logger.warning(
            "Account deletion password lockout triggered for user %s after %s failed attempts",
            user.pk,
            record["count"],
        )
    # The cache entry's own TTL only needs to outlive the stored deadline —
    # it is no longer the source of truth for the window (see
    # _is_delete_locked above), so refreshing it on every write is safe.
    cache.set(key, record, timeout=DELETE_PASSWORD_LOCKOUT_SECONDS)


def _reset_delete_attempts(user):
    cache.delete(_delete_attempts_cache_key(user))


@login_required
def delete_account(request):
    """Password-reconfirmed account deletion request (10-day grace period).

    GET renders the confirmation form. POST verifies the current password
    then records the deletion request via accounts.services.request_deletion
    (see .docs/plans/2026-07-20-deletion-grace-period-plan.md) — the account
    itself is not deleted here; it survives for a 10-day grace period, purged
    later by accounts.management.commands.purge_deleted_accounts unless the
    user logs back in and cancels it. The session is flushed right after the
    request is recorded so the browser's existing cookie stops authenticating
    for the rest of this visit.

    POST is also guarded by a per-user failed-attempt counter (see
    `_is_delete_locked`) so the password check itself cannot be brute-forced.

    Staff accounts are blocked from self-deletion on both GET and POST
    (403) — the header no longer links here for a staff user (account_menu
    dropdown / settings page), but the UI hiding it is not itself a
    guarantee, so the view enforces it directly. Staff removal is a Django
    admin action only (superuser judgment call).
    """
    if request.user.is_staff:
        raise PermissionDenied

    if request.method == "POST":
        if _is_delete_locked(request.user):
            return render(
                request,
                "account/delete_account.html",
                {"field_errors": {"password": DELETE_LOCKOUT_MESSAGE}},
            )

        password = request.POST.get("password", "")
        if not request.user.check_password(password):
            _register_failed_delete_attempt(request.user)
            return render(
                request,
                "account/delete_account.html",
                {"field_errors": {"password": "비밀번호가 올바르지 않습니다."}},
            )

        _reset_delete_attempts(request.user)
        user = request.user
        logger.info("Requesting account deletion user_pk=%s", user.pk)
        services.request_deletion(user)
        logout(request)
        messages.success(
            request,
            "탈퇴가 예약되었습니다. 10일 안에 다시 로그인하면 취소됩니다.",
        )
        return redirect("home")

    return render(request, "account/delete_account.html", {"field_errors": {}})


@login_required
def account_settings(request):
    """Account settings hub: links to allauth's email/password management
    and, for a regular member only, the deletion flow — a staff member has
    no self-deletion path anywhere in the UI."""
    return render(request, "account/settings.html")
