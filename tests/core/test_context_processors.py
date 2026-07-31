"""core.context_processors — google_oauth_configured, support_email 검증.

이 프로젝트에서 Google OAuth 자격증명은 선택 사항이다(config/settings.py
SOCIALACCOUNT_PROVIDERS 참고) — client_id가 비어 있으면 인증 페이지에서
동작하지 않는 구글 버튼을 보여주는 대신 아예 숨겨야 한다.
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
    # config/settings.py의 SUPPORT_EMAIL 기본값(env 미설정, 실제 지원 메일함이
    # 준비될 때까지 예약된 플레이스홀더 도메인).
    settings.SUPPORT_EMAIL = "support@takulife.example"

    assert support_email(None) == {"support_email": "support@takulife.example"}
