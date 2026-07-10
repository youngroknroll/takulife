"""core.context_processors — google_oauth_configured, support_email.

Google OAuth credentials are optional in this project (see
config/settings.py SOCIALACCOUNT_PROVIDERS): a blank client_id must hide the
Google button on the auth pages rather than show a non-functional one.
"""
from core.context_processors import google_oauth_configured, support_email


def test_google_oauth_configured_true_when_client_id_set(settings):
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APPS": [{"client_id": "real-client-id", "secret": "secret", "key": ""}],
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"access_type": "online"},
        }
    }

    assert google_oauth_configured(None) == {"google_oauth_configured": True}


def test_google_oauth_configured_false_when_client_id_blank(settings):
    settings.SOCIALACCOUNT_PROVIDERS = {
        "google": {
            "APPS": [{"client_id": "", "secret": "", "key": ""}],
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"access_type": "online"},
        }
    }

    assert google_oauth_configured(None) == {"google_oauth_configured": False}


def test_support_email_reflects_configured_value(settings):
    settings.SUPPORT_EMAIL = "help@takulife.kr"

    assert support_email(None) == {"support_email": "help@takulife.kr"}


def test_support_email_falls_back_to_placeholder_default(settings):
    # config/settings.py's SUPPORT_EMAIL default (env unset / placeholder
    # domain reserved until the real support inbox is provisioned).
    settings.SUPPORT_EMAIL = "support@takulife.example"

    assert support_email(None) == {"support_email": "support@takulife.example"}
