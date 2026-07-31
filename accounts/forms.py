from allauth.account.forms import AddEmailForm
from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.forms import BooleanField, CharField, PasswordInput
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.safestring import mark_safe


# /legal/ 경로(legal-terms-page / legal-privacy-page, core/views.py)가
# 이미 있으므로 하드코딩 경로 대신 이름으로 참조한다 — 나중에 경로가
# 바뀌어도 여기 링크가 조용히 죽지 않는다. reverse()가 아니라 reverse_lazy를
# 쓰는 이유는 URLconf가 아직 해석되기 전에 이 모듈이 임포트될 수 있기
# 때문이다(예: ACCOUNT_FORMS의 import_string).
_TERMS_AGREEMENT_LABEL = mark_safe(
    '<a href="{terms}" target="_blank" rel="noopener">이용약관</a> 및 '
    '<a href="{privacy}" target="_blank" rel="noopener">개인정보처리방침</a>에 동의합니다.'.format(
        terms=reverse_lazy("legal-terms-page"),
        privacy=reverse_lazy("legal-privacy-page"),
    )
)


class SignupForm(AllauthSignupForm):
    """allauth 가입 폼에 필수 약관/개인정보처리방침 동의 체크박스를
    추가한다(settings.ACCOUNT_FORMS로 등록)."""

    terms_agreed = BooleanField(
        required=True,
        label=_TERMS_AGREEMENT_LABEL,
        error_messages={
            "required": "이용약관 및 개인정보처리방침에 동의해야 가입할 수 있습니다."
        },
    )

    def custom_signup(self, request, user):
        # 가입 폼의 추가 필드를 새 유저에 저장하는 allauth 훅(adapter.save_user
        # 직후 호출). 동의가 *언제* 이뤄졌는지를 증적으로 남긴다.
        super().custom_signup(request, user)
        user.terms_agreed_at = timezone.now()
        user.save(update_fields=["terms_agreed_at"])


class EmailChangeForm(AddEmailForm):
    """allauth의 이메일 추가 폼에 현재 비밀번호 재확인을 추가한다
    (settings.ACCOUNT_FORMS["add_email"]로 등록).

    검사는 save()가 아니라 clean()에 둔다: allauth의 EmailView.form_valid는
    is_valid()가 True일 때만 add_email()/save()를 호출하므로, 여기서
    검증을 실패시키는 것이 실제로 이메일 변경을 막는 방법이다. self.user는
    AddEmailForm의 기반 클래스(allauth UserForm)가 설정한다.
    """

    current_password = CharField(widget=PasswordInput, label="현재 비밀번호")

    def clean_current_password(self):
        current_password = self.cleaned_data["current_password"]
        if not self.user.check_password(current_password):
            raise forms.ValidationError("비밀번호가 올바르지 않습니다.")
        return current_password
