"""스태프 콘솔(/staff/) 접근 관문."""

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.utils import translation


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
        # 스태프 콘솔은 쿠키로 바뀐 방문자 언어와 무관하게 항상 한국어로 운영한다.
        with translation.override("ko"):
            return view_func(request, *args, **kwargs)

    return _wrapped


def staff_api_korean(view_func):
    """스태프 DRF API 뷰 전용 관문. `staff_console_required`는 일반 Django
    뷰에만 적용되고 DRF 뷰는 거치지 않으며, DRF `Response`는 렌더가 뷰
    반환 뒤로 미뤄져 활성 언어가 `with` 블록을 벗어난 뒤 결정되므로, 같은
    블록 안에서 렌더까지 끝내야 지연 번역 값도 한국어로 굳는다."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        with translation.override("ko"):
            response = view_func(request, *args, **kwargs)
            if hasattr(response, "render") and callable(response.render):
                response.render()
            return response

    # 스태프 API 전수 가드 테스트가 이 표지를 확인한다.
    _wrapped.staff_api_korean = True
    return _wrapped


def superuser_console_required(view_func):
    """계정 운영 화면 전용 관문. `staff_console_required` 위에 슈퍼유저
    검사를 더한다 — 계정 플래그 조작 주체는 슈퍼유저로 한정한다."""

    @staff_console_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped
