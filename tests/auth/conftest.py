"""인증 도메인 픽스처: allauth/axes 테스트가 공유하는 일회용 자격증명."""
import secrets
import string

import pytest
from allauth.account.models import EmailAddress


@pytest.fixture(scope="session")
def valid_password():
    """`secrets`로 실행 시점에 조립하는 일회용 비밀번호(대문자+소문자+숫자+
    무작위 꼬리를 보장). 소스에 비밀번호 리터럴이 없으니 시크릿 스캐너가
    걸릴 게 없고, 무작위 접미사와 무관하게 조합 자체가
    AUTH_PASSWORD_VALIDATORS를 만족한다.

    세션 스코프: axes/rate-limit 테스트는 한 테스트 안에서 같은 비밀번호를
    여러 요청에 걸쳐 제출하는데, 값 자체의 무작위성은 검증 대상이 아니므로
    생성된 비밀번호 하나를 실행 전체에서 공유해도 된다. 순수 문자열
    생성만 하고 `db`는 쓰지 않는다 — 함수 스코프 픽스처는 세션 스코프
    픽스처가 의존할 수 없기 때문이다.
    """
    return (
        secrets.choice(string.ascii_uppercase)
        + secrets.choice(string.ascii_lowercase)
        + secrets.choice(string.digits)
        + secrets.token_urlsafe(16)
    )


@pytest.fixture
def make_verified_user(db, django_user_model, valid_password):
    def _make(email=None, password=None, **kwargs):
        email = email or f"user_{secrets.token_hex(4)}@example.com"
        password = password or valid_password
        user = django_user_model.objects.create_user(email=email, password=password, **kwargs)
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        return user

    return _make
