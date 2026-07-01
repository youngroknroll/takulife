"""Access gate for the Staff Console (/staff/).

`staff` is a namespaced view module, not a Django app — this is intentionally
plain and dependency-free (no models, no RBAC/Groups).
"""
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_console_required(view_func):
    """Gate a view to staff users only.

    Mirrors Django's `AccessMixin.handle_no_permission` semantics rather than
    `user_passes_test`: an anonymous user is redirected to the standard site
    login (settings.LOGIN_URL, NOT the Django admin login — the Staff Console
    is a first-class app surface, not an admin-only tool), preserving `next`.
    An authenticated but non-staff user gets a 403 (PermissionDenied) instead
    of being bounced back to login — redirecting them to LOGIN_URL would
    trigger allauth's authenticated-redirect and loop forever, since they are
    already logged in.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped
