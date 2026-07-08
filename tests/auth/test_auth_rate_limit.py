"""Rate-limit protection on authentication endpoints (allauth).

allauth ships ACCOUNT_RATE_LIMITS with sensible defaults already active; these
tests lock that behavior in so a future settings change cannot silently disable
brute-force / signup-flood protection. The autouse ``clear_cache`` fixture
(tests/conftest.py) resets the cache-backed counters between tests.

Two distinct enforcement shapes are exercised, matching allauth's design:
- login_failed -> the login form refuses further authentication (even with the
  correct password) once the per-account window is exhausted (HTTP 200 + a
  localized non-field error, NOT a 429).
- signup / reset_password -> the view raises a 429 rendered via ``429.html``.
"""
import secrets
import string

import pytest
from allauth.account.models import EmailAddress
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


def _verified_user(django_user_model, email):
    user = django_user_model.objects.create_user(email=email, password=VALID_PASSWORD)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def _is_authenticated(client):
    """A protected page returns 200 when logged in, 302 (to login) otherwise."""
    return client.get("/archive/").status_code == 200


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "2/m/key"})
def test_failed_logins_block_further_attempts_even_with_correct_password(
    client, django_user_model
):
    """After the per-account failure window is exhausted, the login form refuses
    to authenticate — even the correct password is rejected — which is what
    actually stops an online brute-force attack."""
    _verified_user(django_user_model, "victim@example.com")

    # Exhaust the 2/m/key window with wrong passwords.
    for _ in range(2):
        resp = client.post(
            "/accounts/login/",
            {"login": "victim@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 200, resp.status_code

    # The correct password is now refused: still on the form, not logged in.
    blocked = client.post(
        "/accounts/login/",
        {"login": "victim@example.com", "password": VALID_PASSWORD},
    )
    assert blocked.status_code == 200
    form = blocked.context["form"]
    assert form.non_field_errors(), "expected a throttle error on the login form"
    assert not _is_authenticated(client), "rate-limited login must not grant a session"


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"signup": "2/m/ip"})
def test_signup_is_rate_limited(client):
    """Repeated signups from one IP are throttled with a 429 once exceeded."""
    for i in range(2):
        resp = client.post(
            "/accounts/signup/",
            {
                "email": f"newuser{i}@example.com",
                "password1": VALID_PASSWORD,
                "password2": VALID_PASSWORD,
            },
        )
        assert resp.status_code in (200, 302), resp.status_code

    throttled = client.post(
        "/accounts/signup/",
        {
            "email": "newuser99@example.com",
            "password1": VALID_PASSWORD,
            "password2": VALID_PASSWORD,
        },
    )
    assert throttled.status_code == 429, throttled.status_code


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"reset_password": "2/m/ip"})
def test_password_reset_request_is_rate_limited(client, django_user_model):
    """Repeated password-reset requests from one IP are throttled with a 429."""
    _verified_user(django_user_model, "reset@example.com")

    for _ in range(2):
        resp = client.post("/accounts/password/reset/", {"email": "reset@example.com"})
        assert resp.status_code in (200, 302), resp.status_code

    throttled = client.post(
        "/accounts/password/reset/", {"email": "reset@example.com"}
    )
    assert throttled.status_code == 429, throttled.status_code


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"signup": "1/m/ip"})
def test_rate_limited_response_renders_localized_page(client):
    """The 429 is served through the project's Korean ``429.html`` template,
    not allauth's bare English fallback."""
    client.post(
        "/accounts/signup/",
        {"email": "first@example.com", "password1": VALID_PASSWORD, "password2": VALID_PASSWORD},
    )
    throttled = client.post(
        "/accounts/signup/",
        {"email": "second@example.com", "password1": VALID_PASSWORD, "password2": VALID_PASSWORD},
    )
    assert throttled.status_code == 429
    assert "429.html" in [t.name for t in throttled.templates if t.name]
    body = throttled.content.decode("utf-8", "ignore")
    assert "요청이 너무 많습니다" in body
