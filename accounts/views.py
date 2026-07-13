from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

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

    Uses `cache.add` (sets the key only if absent) followed by `cache.incr`
    so the 15-minute window starts on the *first* failure and is not
    refreshed by later failures — a simple fixed window, not a sliding one.
    Relies on the default (LocMem) cache: single-process only, and the
    counter resets on process restart. Fine for a single-instance
    deployment; a multi-instance deployment needs a shared cache backend
    (e.g. Redis) for this counter to stay effective.
    """
    return cache.get(_delete_attempts_cache_key(user), 0) >= MAX_DELETE_PASSWORD_ATTEMPTS


def _register_failed_delete_attempt(user):
    key = _delete_attempts_cache_key(user)
    cache.add(key, 0, timeout=DELETE_PASSWORD_LOCKOUT_SECONDS)
    cache.incr(key)


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
