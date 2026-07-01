"""django-axes brute-force lockout on the login endpoint.

axes adds a durable IP lockout on top of allauth's per-window throttle. These
tests disable allauth's own login_failed limit (set very high) so the behavior
under test is unambiguously axes'.

The autouse ``clear_cache`` fixture handles the cache; axes stores attempts in
the DB (rolled back per test), and ``axes_reset`` guarantees a clean slate.
"""
import secrets
import string

import pytest
from allauth.account.models import EmailAddress
from axes.utils import reset
from django.test import override_settings

# Throwaway password assembled at runtime from `secrets` (guaranteed upper +
# lower + digit + random tail). No password literal lives in source, so secret
# scanners have nothing to flag; the mix satisfies AUTH_PASSWORD_VALIDATORS.
VALID_PASSWORD = (
    secrets.choice(string.ascii_uppercase)
    + secrets.choice(string.ascii_lowercase)
    + secrets.choice(string.digits)
    + secrets.token_urlsafe(16)
)


@pytest.fixture
def axes_reset():
    reset()
    yield
    reset()


def _verified(model, email):
    user = model.objects.create_user(email=email, password=VALID_PASSWORD)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


@pytest.mark.django_db
@override_settings(AXES_FAILURE_LIMIT=3, ACCOUNT_RATE_LIMITS={"login_failed": "1000/m/key"})
def test_axes_locks_out_ip_after_repeated_failed_logins(
    client, django_user_model, axes_reset
):
    """After AXES_FAILURE_LIMIT failed logins the IP is locked out — a further
    attempt is blocked with 429 even when the password is correct."""
    _verified(django_user_model, "target@example.com")

    for _ in range(3):
        client.post(
            "/accounts/login/",
            {"login": "target@example.com", "password": "wrong-password"},
        )

    locked = client.post(
        "/accounts/login/",
        {"login": "target@example.com", "password": VALID_PASSWORD},
    )
    assert locked.status_code == 429, locked.status_code
    assert client.get("/archive/").status_code != 200, "locked-out login must not authenticate"


@pytest.mark.django_db
@override_settings(AXES_FAILURE_LIMIT=3, ACCOUNT_RATE_LIMITS={"login_failed": "1000/m/key"})
def test_axes_lockout_renders_korean_template(client, django_user_model, axes_reset):
    """The lockout response is served via templates/account/lockout.html."""
    _verified(django_user_model, "target2@example.com")

    for _ in range(3):
        client.post(
            "/accounts/login/",
            {"login": "target2@example.com", "password": "wrong-password"},
        )
    locked = client.post(
        "/accounts/login/",
        {"login": "target2@example.com", "password": "wrong-password"},
    )
    assert locked.status_code == 429
    body = locked.content.decode("utf-8", "ignore")
    assert "로그인 시도가 너무 많습니다" in body
