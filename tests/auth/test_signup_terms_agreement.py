"""회원가입은 이용약관/개인정보처리방침 명시적 동의를 요구한다
(accounts.forms.SignupForm, ACCOUNT_FORMS 참고)."""
from django.urls import reverse
from django.utils import timezone

import pytest

pytestmark = pytest.mark.web

SIGNUP_URL = "/accounts/signup/"


@pytest.mark.django_db
def test_약관_동의_없이_회원가입하면_가입이_거부되고_사용자가_생성되지_않는다(client, django_user_model, valid_password):
    response = client.post(
        SIGNUP_URL,
        {
            "email": "noagreement@example.com",
            "password1": valid_password,
            "password2": valid_password,
        },
    )

    # "이메일을 확인하세요" 페이지로 리다이렉트되지 않고, 폼 오류와 함께
    # 다시 렌더된다.
    assert response.status_code == 200
    assert not django_user_model.objects.filter(email="noagreement@example.com").exists()


@pytest.mark.django_db
def test_약관에_동의하고_회원가입하면_사용자가_생성되고_동의_시각이_기록된다(
    client, django_user_model, valid_password
):
    before = timezone.now()

    response = client.post(
        SIGNUP_URL,
        {
            "email": "agreed@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )

    assert response.status_code == 302
    user = django_user_model.objects.get(email="agreed@example.com")
    assert user.terms_agreed_at is not None
    assert user.terms_agreed_at >= before


@pytest.mark.django_db
def test_회원가입_페이지는_약관_동의_체크박스를_렌더링한다(client):
    response = client.get(SIGNUP_URL)

    assert response.status_code == 200
    body = response.content.decode("utf-8", "ignore")
    assert 'name="terms_agreed"' in body


@pytest.mark.django_db
def test_약관_동의_라벨은_이용약관과_개인정보처리방침_페이지로_연결된다(client):
    """라벨의 href는 하드코딩된 문자열이 아니라 reverse_lazy(accounts/forms.py)로
    만들어진다 — 나중에 /legal/ 라우트 이름이 바뀌어도 가입 페이지에 죽은
    링크가 조용히 남지 않도록 지킨다."""
    response = client.get(SIGNUP_URL)

    body = response.content.decode("utf-8", "ignore")
    assert f'href="{reverse("legal-terms-page")}"' in body
    assert f'href="{reverse("legal-privacy-page")}"' in body
