from allauth.account.models import EmailAddress
from allauth.decorators import rate_limit
from allauth.socialaccount.views import SignupView as AllauthSocialSignupView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache

from . import services


@method_decorator(rate_limit(action="signup"), name="dispatch")
class SocialSignupView(AllauthSocialSignupView):
    """allauth 소셜 가입 뷰는 로컬 가입 뷰(allauth account/views.py의
    SignupView)와 달리 자체 레이트리밋이 없어, 같은 signup 한도를 여기서
    선등록으로 건다(config/urls.py)."""


@login_required
def account_settings(request):
    """계정 설정 허브: allauth의 이메일/비밀번호 관리로 연결하고, 일반
    회원에게만 탈퇴 흐름을 보여준다 — 스태프는 UI 어디에도 자율 탈퇴
    경로가 없다."""
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
    """탈퇴 완료 안내. web.views.account.delete_account가 logout() 이후
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
