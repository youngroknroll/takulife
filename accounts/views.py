from allauth.account.models import EmailAddress
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache

from . import services


@login_required
def account_settings(request):
    """Account settings hub: links to allauth's email/password management
    and, for a regular member only, the deletion flow — a staff member has
    no self-deletion path anywhere in the UI."""
    user = request.user
    email_verified = EmailAddress.objects.filter(user=user, verified=True).exists()
    return render(
        request,
        "account/settings.html",
        {
            "account_email": user.email,
            "email_verified": email_verified,
            "password_changed_display": services.format_password_changed_display(
                user.password_changed_at
            ),
            "date_joined": user.date_joined,
        },
    )


@never_cache
def delete_account_done(request):
    """탈퇴 완료 안내. core.views.account.delete_account가 logout() 이후
    세션에 적재한 신청 시각·삭제 예정일을 pop해서 보여준다 — 세션 키가
    없으면(직접 URL 접근) 홈으로 보낸다. 세션은 JSON 직렬화라 datetime을 그대로
    왕복시키지 못하므로 ISO 문자열로 저장했다가 여기서 다시 파싱한다.
    @never_cache는 탈퇴한 사용자가 뒤로가기로 이 화면을 캐시에서 다시 보는
    것을 막는다."""
    deletion_info = request.session.pop(services.DELETE_DONE_SESSION_KEY, None)
    if deletion_info is None:
        return redirect("home")
    return render(
        request,
        "account/delete_done.html",
        {
            "deletion_requested_at": parse_datetime(deletion_info["requested_at"]),
            "deletion_scheduled_for": parse_datetime(deletion_info["scheduled_for"]),
        },
    )
