"""Auth-domain fixtures: shared throwaway credentials for allauth/axes tests."""
import secrets
import string

import pytest
from allauth.account.models import EmailAddress


@pytest.fixture(scope="session")
def valid_password():
    """A throwaway password assembled at runtime from `secrets` (guaranteed
    upper + lower + digit + random tail). No password literal lives in
    source, so secret scanners have nothing to flag; the mix satisfies
    AUTH_PASSWORD_VALIDATORS regardless of the random suffix.

    Session-scoped: axes/rate-limit tests submit the same password across
    several requests within a test, and the value's own randomness is not
    itself under test — so one generated password can be shared for the
    whole run. Pure string generation only (no `db`), since a function-scoped
    fixture cannot be depended on from a session-scoped one.
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
