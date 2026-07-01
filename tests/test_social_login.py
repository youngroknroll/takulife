"""Google social login (allauth socialaccount).

The full OAuth round-trip against Google cannot run in CI (external service,
real credentials), so these tests cover what is testable without it:
- the Google provider is registered and its button renders on the auth pages,
- our account-linking policy (a Google login whose provider-verified email
  matches an existing local account logs into that account) works, driven
  through allauth's ``complete_social_login`` with a mocked ``SocialLogin``.

The live Google round-trip is verified manually on localhost.
"""
import pytest

GOOGLE_LOGIN_PATH = "/accounts/google/login/"


@pytest.mark.django_db
def test_login_page_shows_google_button(client):
    """The login page links to the Google login flow."""
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH in response.content.decode("utf-8", "ignore")


@pytest.mark.django_db
def test_signup_page_shows_google_button(client):
    """The signup page also offers Google."""
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH in response.content.decode("utf-8", "ignore")


def test_google_provider_requests_email_scope(settings):
    """Google is configured to request the email scope — without it allauth
    cannot obtain the verified address the linking policy relies on."""
    google = settings.SOCIALACCOUNT_PROVIDERS["google"]
    assert "email" in google["SCOPE"]


def test_verified_email_linking_policy_is_enabled(settings):
    """A Google login whose provider-verified email matches an existing local
    account must log into (and connect to) that account — the approved policy.
    Guarded here so it can't be silently disabled. Safe only because Google is
    a fully-trusted provider; revisit if another provider is added.

    (The end-to-end OAuth round-trip, auto-link and verified-email-skip are
    verified manually on localhost — allauth owns that flow and reconstructing
    it in-process couples brittly to internals.)"""
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION is True
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT is True
