"""core.context_processors — google_oauth_configured.

Google OAuth credentials are optional in this project (see
config/settings.py SOCIALACCOUNT_PROVIDERS): a blank client_id must hide the
Google button on the auth pages rather than show a non-functional one.
"""
from core.context_processors import google_oauth_configured


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
