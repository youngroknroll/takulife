"""가입은 닉네임 입력을 필수로 요구한다(트랙 29 NICK-05)."""
from allauth.socialaccount.models import SocialLogin
from django.test import RequestFactory

import pytest

from accounts.adapters import AccountAdapter
from accounts.forms import SocialSignupForm, TermsAgreementFormMixin
from accounts.validators import normalize_nickname

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_닉네임_없이_가입하면_가입이_거부되고_사용자가_생성되지_않는다(
    client, django_user_model, valid_password
):
    resp = client.post(
        "/accounts/signup/",
        data={
            "email": "no-nickname@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )

    assert resp.status_code == 200
    assert django_user_model.objects.filter(email="no-nickname@example.com").exists() is False
    assert "닉네임을 입력해 주세요." in resp.content.decode()


@pytest.mark.django_db
def test_유효한_닉네임으로_가입하면_사용자_닉네임에_반영된다(
    client, django_user_model, valid_password
):
    resp = client.post(
        "/accounts/signup/",
        data={
            "email": "with-nickname@example.com",
            "nickname": "타쿠러",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )

    assert resp.status_code == 302
    user = django_user_model.objects.get(email="with-nickname@example.com")
    assert user.nickname == "타쿠러"


@pytest.mark.django_db
def test_대소문자만_다른_기존_닉네임으로_가입하면_거부된다(
    client, django_user_model, make_user, valid_password
):
    make_user(nickname="Taku")

    resp = client.post(
        "/accounts/signup/",
        data={
            "email": "dupe-nickname@example.com",
            "nickname": "taku",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )

    assert resp.status_code == 200
    assert django_user_model.objects.filter(email="dupe-nickname@example.com").exists() is False
    assert "이미 사용 중인 닉네임입니다." in resp.content.decode()


@pytest.mark.django_db
def test_소셜_가입시_유효한_닉네임을_제출하면_사용자_닉네임에_반영된다(django_user_model):
    user = django_user_model(email="social-nick@example.com")
    sociallogin = SocialLogin(user=user)
    form = SocialSignupForm(
        data={
            "email": "social-nick@example.com",
            "nickname": "소셜러",
            "terms_agreed": "on",
        },
        sociallogin=sociallogin,
    )
    assert form.is_valid() is True

    AccountAdapter().save_user(RequestFactory().post("/"), user, form)

    assert user.nickname == "소셜러"
    assert django_user_model.objects.get(email="social-nick@example.com").nickname == "소셜러"


@pytest.mark.django_db
def test_가입_사전_중복_검사를_통과한_뒤_DB_제약에_걸리면_중복_오류로_안내된다(
    client, django_user_model, make_user, valid_password, monkeypatch
):
    # 폼의 iexact 사전 검사를 건너뛰어 두 요청이 거의 동시에 도착한
    # 경쟁 창을 재현한다 — 최후 방어는 DB UniqueConstraint다.
    monkeypatch.setattr(
        TermsAgreementFormMixin,
        "clean_nickname",
        lambda self: normalize_nickname(self.cleaned_data["nickname"]),
    )
    make_user(nickname="Taku")

    resp = client.post(
        "/accounts/signup/",
        data={
            "email": "race-nickname@example.com",
            "nickname": "taku",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )

    assert resp.status_code == 200
    assert "이미 사용 중인 닉네임입니다." in resp.content.decode()
    assert django_user_model.objects.filter(email="race-nickname@example.com").exists() is False
