"""트랙 43-1 UI 다국어 기반 — 설정 모듈 핀(LANGUAGE_CODE/LANGUAGES/LOCALE_PATHS/
LocaleMiddleware 순서/i18n 컨텍스트 프로세서/언어 쿠키 보안 속성)."""

import importlib

import pytest

pytestmark = pytest.mark.contract


# I18N-1
def test_설정_모듈의_LANGUAGE_CODE는_ko로_정리된다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.LANGUAGE_CODE == "ko"


# I18N-2
def test_설정_모듈의_LANGUAGES는_4개_언어를_선언한다():
    settings_module = importlib.import_module("config.settings")

    codes = {code for code, _ in settings_module.LANGUAGES}

    assert codes == {"ko", "en", "ja", "zh-hans"}
    assert len(settings_module.LANGUAGES) == 4


# I18N-3
def test_설정_모듈의_LOCALE_PATHS는_존재하는_디렉터리를_가리킨다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.LOCALE_PATHS == [settings_module.BASE_DIR / "locale"]
    assert settings_module.LOCALE_PATHS[0].is_dir()


# I18N-4
def test_LocaleMiddleware는_SessionMiddleware_다음_CommonMiddleware_앞에_등록된다():
    settings_module = importlib.import_module("config.settings")

    middleware = settings_module.MIDDLEWARE
    session_index = middleware.index("django.contrib.sessions.middleware.SessionMiddleware")
    locale_index = middleware.index("django.middleware.locale.LocaleMiddleware")

    assert locale_index == session_index + 1
    assert middleware[locale_index + 1] == "django.middleware.common.CommonMiddleware"


# I18N-5
def test_TEMPLATES_컨텍스트_프로세서는_i18n을_포함한다():
    settings_module = importlib.import_module("config.settings")

    context_processors = settings_module.TEMPLATES[0]["OPTIONS"]["context_processors"]

    assert "django.template.context_processors.i18n" in context_processors


# I18N-6
def test_언어_쿠키는_보안_쿠키_설정과_SameSite_Lax_HttpOnly를_따른다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.LANGUAGE_COOKIE_SECURE == settings_module.load_secure_cookies()
    assert settings_module.LANGUAGE_COOKIE_SAMESITE == "Lax"
    assert settings_module.LANGUAGE_COOKIE_HTTPONLY is True
