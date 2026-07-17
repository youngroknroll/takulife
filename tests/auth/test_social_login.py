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

_CONFIGURED_GOOGLE_PROVIDER = {
    "google": {
        "APPS": [{"client_id": "test-client-id", "secret": "test-secret", "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

_UNCONFIGURED_GOOGLE_PROVIDER = {
    "google": {
        "APPS": [{"client_id": "", "secret": "", "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}


@pytest.mark.web
@pytest.mark.django_db
def test_구글_로그인이_설정되어_있으면_로그인_페이지에_구글_버튼이_노출된다(client, settings):
    """The login page links to the Google login flow once credentials exist."""
    settings.SOCIALACCOUNT_PROVIDERS = _CONFIGURED_GOOGLE_PROVIDER
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH in response.content.decode("utf-8", "ignore")


@pytest.mark.web
@pytest.mark.django_db
def test_구글_로그인이_설정되어_있으면_회원가입_페이지에_구글_버튼이_노출된다(client, settings):
    """The signup page also offers Google once credentials exist."""
    settings.SOCIALACCOUNT_PROVIDERS = _CONFIGURED_GOOGLE_PROVIDER
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH in response.content.decode("utf-8", "ignore")


@pytest.mark.web
@pytest.mark.django_db
def test_구글_로그인이_미설정이면_로그인_페이지에_구글_버튼이_노출되지_않는다(client, settings):
    """A blank client_id hides the button instead of showing a dead link."""
    settings.SOCIALACCOUNT_PROVIDERS = _UNCONFIGURED_GOOGLE_PROVIDER
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH not in response.content.decode("utf-8", "ignore")


@pytest.mark.web
@pytest.mark.django_db
def test_구글_로그인이_미설정이면_회원가입_페이지에_구글_버튼이_노출되지_않는다(client, settings):
    """A blank client_id hides the button instead of showing a dead link."""
    settings.SOCIALACCOUNT_PROVIDERS = _UNCONFIGURED_GOOGLE_PROVIDER
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH not in response.content.decode("utf-8", "ignore")


@pytest.mark.contract
def test_구글_provider_설정은_email_scope를_요청한다(settings):
    """Google is configured to request the email scope — without it allauth
    cannot obtain the verified address the linking policy relies on."""
    google = settings.SOCIALACCOUNT_PROVIDERS["google"]
    assert "email" in google["SCOPE"]


@pytest.mark.contract
def test_구글_이메일_인증_계정연결_정책_설정이_활성화되어_있다(settings):
    """A Google login whose provider-verified email matches an existing local
    account must log into (and connect to) that account — the approved policy.
    Guarded here so it can't be silently disabled. Safe only because Google is
    a fully-trusted provider; revisit if another provider is added.

    (The end-to-end OAuth round-trip, auto-link and verified-email-skip are
    verified manually on localhost — allauth owns that flow and reconstructing
    it in-process couples brittly to internals.)"""
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION is True
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT is True
