"""소셜 가입도 이용약관/개인정보처리방침 명시적 동의를 요구한다
(accounts.forms.SocialSignupForm 참고)."""
from allauth.socialaccount.models import SocialLogin
from django.test import RequestFactory
from django.utils import timezone

import pytest

from accounts.forms import SocialSignupForm

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_소셜_가입_폼에_약관_동의_없이_제출하면_폼이_거부되고_지정된_오류_메시지를_담는다(django_user_model):
    user = django_user_model(email="social-reject@example.com")
    sociallogin = SocialLogin(user=user)

    form = SocialSignupForm(data={"email": "social-reject@example.com"}, sociallogin=sociallogin)

    assert form.is_valid() is False
    assert "이용약관 및 개인정보처리방침에 동의해야 가입할 수 있습니다." in form.errors["terms_agreed"]


@pytest.mark.django_db
def test_소셜_가입_폼이_동의와_함께_처리되면_사용자의_동의_시각이_기록된다(django_user_model):
    """이 테스트는 소셜 로그인 provider 어댑터 왕복(공급자 콜백, 세션에 저장된
    sociallogin 복원 등)을 구동하지 않는다 — 그 배관은 전적으로 allauth 자체의
    내부 계약이라(tests/auth/test_password_changed_at.py의 A3과 같은 판단),
    여기서는 우리 폼의 custom_signup 훅이 동의 시각을 기록하는지만 직접
    확인한다."""
    user = django_user_model.objects.create_user(email="social-agree@example.com", password=None)
    sociallogin = SocialLogin(user=user)
    form = SocialSignupForm(
        data={"email": "social-agree@example.com", "terms_agreed": "on"},
        sociallogin=sociallogin,
    )
    assert form.is_valid() is True
    before = timezone.now()

    form.custom_signup(RequestFactory().post("/"), user)

    assert user.terms_agreed_at is not None
    assert user.terms_agreed_at >= before
