"""User.password_changed_at — allauth의 비밀번호 생애주기 시그널 3종
(password_changed / password_set / password_reset) 중 하나가 발화할 때마다
accounts.signals에 연결된 accounts.services.record_password_change를 통해
기록된다.

A1/A2는 실제 HTTP 뷰를 구동해 Django 앱 레지스트리(accounts/apps.py의
시그널 임포트)를 통한 배선까지 종단으로 증명한다 —
test_account_deletion.py의 HTTP 수준 DEL 테스트와 같은 방식이다. A3은
그렇게 하지 않는다 — 이유는 그 독스트링 참고.
"""
import secrets

import pytest
from allauth.account.signals import password_reset
from django.test import RequestFactory
from django.utils import timezone

PASSWORD_CHANGE_URL = "/accounts/password/change/"
PASSWORD_SET_URL = "/accounts/password/set/"


def _fresh_password():
    # 어떤 픽스처 제공 비밀번호와도 다르면서 AUTH_PASSWORD_VALIDATORS(길이,
    # 숫자만 아님, 흔하지 않음)를 확실히 만족하는 비밀번호.
    return "Np-" + secrets.token_urlsafe(12)


@pytest.mark.django_db
def test_비밀번호_변경_시_변경_시각이_기록된다(client, make_user, valid_password):
    """A1: /accounts/password/change/(oldpassword/password1/password2)."""
    user = make_user(password=valid_password)
    client.force_login(user)
    before = timezone.now()
    new_password = _fresh_password()

    response = client.post(
        PASSWORD_CHANGE_URL,
        {
            "oldpassword": valid_password,
            "password1": new_password,
            "password2": new_password,
        },
    )
    assert response.status_code == 302

    user.refresh_from_db()
    assert user.password_changed_at is not None
    assert user.password_changed_at >= before


@pytest.mark.django_db
def test_비밀번호_최초_설정_시에도_변경_시각이_기록된다(client, make_user):
    """A2: make_user() 기본값(usable password 없음) 그대로 /accounts/password/set/."""
    user = make_user()
    client.force_login(user)
    before = timezone.now()
    new_password = _fresh_password()

    response = client.post(
        PASSWORD_SET_URL,
        {"password1": new_password, "password2": new_password},
    )
    assert response.status_code == 302

    user.refresh_from_db()
    assert user.password_changed_at is not None
    assert user.password_changed_at >= before


@pytest.mark.django_db
def test_비밀번호_재설정_신호가_발화하면_변경_시각이_기록된다(make_user):
    """A3: A1/A2와 달리 이 테스트는 실제 reset-key/reset-code HTTP 흐름을
    구동하지 않는다. 그 흐름은 세션/토큰을 주고받는 2단계 왕복이고
    전적으로 allauth 자체의 내부 계약(키 검증, ResetPasswordKeyForm 등)이라
    — 여기서 그걸 다시 구현하면 우리 코드가 아니라 allauth를 검증하는
    셈이 되고, allauth의 내부 URL/토큰 장치에 이 테스트가 과도하게
    결합된다(tests/auth/test_account_deletion.py의 DEL-05가 django-axes의
    user_logged_in 리시버를 통해 POST하는 대신
    cancel_pending_deletion_on_login을 직접 보내는 것과 같은 판단이다).
    리시버 로직 자체(record_password_change로 password_changed_at을 쓰는
    것)는 이미 A1과 A2의 HTTP 경로가 종단으로 증명했다 — password_reset에
    대해 검증되지 않은 채 남은 유일한 것은 *우리* 리시버가 실제로
    allauth의 password_reset 시그널을 구독하고 있는지인데, 여기서 시그널을
    직접 보내는 것이 정확히 그걸 증명한다.
    """
    user = make_user()
    before = timezone.now()

    password_reset.send(
        sender=type(user),
        request=RequestFactory().post("/"),
        user=user,
    )

    user.refresh_from_db()
    assert user.password_changed_at is not None
    assert user.password_changed_at >= before
