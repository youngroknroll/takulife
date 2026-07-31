"""스태프 콘솔(/staff/) 접근 관문."""
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_console_required(view_func):
    """스태프만 통과시키는 뷰 관문.

    미인증 사용자는 next를 유지한 채 사이트 로그인으로 보낸다. 인증은
    됐지만 스태프가 아니면 403을 준다 — 로그인 화면으로 다시 보내면 이미
    로그인된 상태라 allauth가 리다이렉트를 무한히 반복시키기 때문이다.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped
