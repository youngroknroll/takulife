"""User.password_changed_at — recorded whenever allauth fires one of its
three password-lifecycle signals (password_changed / password_set /
password_reset), via accounts.services.record_password_change wired in
accounts.signals (see .docs mypage brief).

A1/A2 drive the real HTTP views so the wiring through Django's app registry
(accounts/apps.py signal import) is proven end to end, same as
test_account_deletion.py's HTTP-level DEL tests. A3 does not — see its
docstring for why.
"""
import secrets

import pytest
from allauth.account.signals import password_reset
from django.test import RequestFactory
from django.utils import timezone

PASSWORD_CHANGE_URL = "/accounts/password/change/"
PASSWORD_SET_URL = "/accounts/password/set/"


def _fresh_password():
    # A password distinct from any fixture-provided one and guaranteed to
    # satisfy AUTH_PASSWORD_VALIDATORS (length + non-numeric + not common).
    return "Np-" + secrets.token_urlsafe(12)


@pytest.mark.django_db
def test_비밀번호_변경_시_변경_시각이_기록된다(client, make_user, valid_password):
    """A1: /accounts/password/change/ (oldpassword/password1/password2)."""
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
    """A3: unlike A1/A2, this does not drive the real reset-key/reset-code
    HTTP flow. That flow is a two-step, session/token-carrying round trip
    that is entirely allauth's own internal contract (key verification,
    ResetPasswordKeyForm, etc.) — re-deriving it here would mostly test
    allauth, not our code, and would over-couple this test to allauth's
    internal URL/token machinery (same call made for DEL-05 in
    tests/auth/test_account_deletion.py, which sends
    cancel_pending_deletion_on_login directly rather than posting through
    django-axes' user_logged_in receiver). The receiver logic itself
    (writing password_changed_at via record_password_change) is already
    proven end-to-end by A1 and A2's HTTP paths; the only thing left
    unverified for password_reset specifically is that *our* receiver is
    actually subscribed to allauth's password_reset signal, which is exactly
    what sending the signal directly here proves.
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
