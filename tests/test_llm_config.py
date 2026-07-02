from django.conf import settings
from django.test import override_settings

import pytest

from core.llm.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMRequestError,
    LLMResponseError,
    LLMTimeoutError,
)


def test_llm_model_setting_is_a_haiku_model():
    assert "haiku" in settings.LLM_MODEL.lower()


def test_llm_timeout_seconds_is_ten():
    assert settings.LLM_TIMEOUT_SECONDS == 10


@override_settings(ANTHROPIC_API_KEY="")
def test_get_api_key_raises_when_blank():
    from core.llm.config import get_api_key

    with pytest.raises(LLMConfigurationError):
        get_api_key()


@override_settings(ANTHROPIC_API_KEY="configured-key")
def test_get_api_key_returns_configured_value():
    from core.llm.config import get_api_key

    assert get_api_key() == "configured-key"


@override_settings(ANTHROPIC_API_KEY="   ")
def test_get_api_key_raises_when_whitespace_only():
    """OS env vars are read directly by settings (bypassing _get_env's strip
    when the value comes from the process environment rather than .env), so a
    whitespace-only key must be treated the same as blank."""
    from core.llm.config import get_api_key

    with pytest.raises(LLMConfigurationError):
        get_api_key()


@pytest.mark.parametrize(
    "exception_class",
    [LLMConfigurationError, LLMTimeoutError, LLMRequestError, LLMResponseError],
)
def test_llm_exceptions_subclass_llm_error(exception_class):
    assert issubclass(exception_class, LLMError)
