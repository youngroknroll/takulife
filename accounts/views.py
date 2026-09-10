from allauth.account.models import EmailAddress
from allauth.account.views import SignupView as AllauthSignupView
from allauth.decorators import rate_limit
from allauth.socialaccount.views import SignupView as AllauthSocialSignupView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache

from . import services
from .forms import NicknameChangeForm


class NicknameConflictFormMixin:
    """가입 폼의 사전 중복 검사와 실제 저장 사이의 경쟁 창에서 DB
    UniqueConstraint가 걸리면 500 대신 nickname 필드 오류로 보여준다.
    allauth의 form_valid가 저장과 인증 메일 발송(complete_signup)까지
    하므로, atomic 블록으로 감싸 실패 시 이메일 발송 이전 상태로 통째로
    되돌린다."""

    def form_valid(self, form):
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError as exc:
            if not services.is_nickname_conflict(exc):
                raise
            form.add_error("nickname", services.NICKNAME_DUPLICATE_MESSAGE)
            return self.form_invalid(form)


class SignupView(NicknameConflictFormMixin, AllauthSignupView):
    """로컬 이메일 가입 뷰. allauth SignupView.dispatch가 이미 자체
    레이트리밋을 걸므로 여기서 다시 걸지 않는다(SocialSignupView와의 차이).
    url name(account_signup)은 allauth 내부 reverse가 참조하므로 그대로
    유지하고, 경쟁 창 IntegrityError 번역만 이 뷰가 선등록으로 추가한다
    (config/urls.py)."""


@method_decorator(rate_limit(action="signup"), name="dispatch")
class SocialSignupView(NicknameConflictFormMixin, AllauthSocialSignupView):
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


@login_required
def nickname_change(request):
    """계정 설정의 닉네임 변경 화면."""
    if request.method == "POST":
        form = NicknameChangeForm(request.user, request.POST)
        if services.is_nickname_change_throttled(request.user):
            form.add_error(None, services.NICKNAME_CHANGE_THROTTLE_MESSAGE)
        elif form.is_valid():
            try:
                with transaction.atomic():
                    request.user.nickname = form.cleaned_data["nickname"]
                    request.user.save(update_fields=["nickname"])
            except IntegrityError as exc:
                if not services.is_nickname_conflict(exc):
                    raise
                # 실패한 저장 시도가 메모리 상의 request.user.nickname을
                # 이미 바꿔 놓았으므로, 재렌더되는 헤더·메뉴가 실패한 값을
                # 보여주지 않도록 DB의 원래 값으로 되돌린다.
                request.user.refresh_from_db(fields=["nickname"])
                form.add_error("nickname", services.NICKNAME_DUPLICATE_MESSAGE)
            else:
                services.register_nickname_change(request.user)
                messages.success(request, "닉네임이 변경되었습니다.")
                return redirect("account-nickname-page")
    else:
        form = NicknameChangeForm(request.user)
    return render(request, "account/nickname_change.html", {"form": form})


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
