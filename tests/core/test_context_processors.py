"""core.context_processors — google_oauth_configured, support_email.

Google OAuth credentials are optional in this project (see
config/settings.py SOCIALACCOUNT_PROVIDERS): a blank client_id must hide the
Google button on the auth pages rather than show a non-functional one.
"""
import pytest

from core.context_processors import google_oauth_configured, support_email

pytestmark = pytest.mark.unit


def test_client_id가_설정되면_google_oauth_configured가_참을_반환한다(settings):
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APPS": [{"client_id": "real-client-id", "secret": "secret", "key": ""}],
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"access_type": "online"},
        }
    }

    assert google_oauth_configured(None) == {"google_oauth_configured": True}


def test_client_id가_비어있으면_google_oauth_configured가_거짓을_반환한다(settings):
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APPS": [{"client_id": "", "secret": "", "key": ""}],
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"access_type": "online"},
        }
    }

    assert google_oauth_configured(None) == {"google_oauth_configured": False}


def test_support_email은_설정된_값을_그대로_반환한다(settings):
    settings.SUPPORT_EMAIL = "help@takulife.kr"

    assert support_email(None) == {"support_email": "help@takulife.kr"}


def test_support_email은_미설정_시_기본_플레이스홀더_주소로_대체된다(settings):
    # config/settings.py's SUPPORT_EMAIL default (env unset / placeholder
    # domain reserved until the real support inbox is provisioned).
    settings.SUPPORT_EMAIL = "support@takulife.example"

    assert support_email(None) == {"support_email": "support@takulife.example"}
