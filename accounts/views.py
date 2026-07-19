import logging
import time

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

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
    """Password-reconfirmed account deletion.

    GET renders the confirmation form. POST verifies the current password
    before deleting the account; owned archive rows and their media files
    cascade via each model's on_delete=CASCADE FK plus the archive.signals
    post_delete cleanup (see archive/models.py, archive/signals.py) — this
    view does not re-implement that cleanup. The session is flushed right
    after the delete so the browser's existing cookie can never keep
    authenticating the now-gone account.

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
        user.delete()
        logout(request)
        messages.success(request, "회원 탈퇴가 완료되었습니다.")
        return redirect("home")

    return render(request, "account/delete_account.html", {"field_errors": {}})


@login_required
def account_settings(request):
    """Account settings hub: links to allauth's email/password management
    and, for a regular member only, the deletion flow — a staff member has
    no self-deletion path anywhere in the UI."""
    return render(request, "account/settings.html")
