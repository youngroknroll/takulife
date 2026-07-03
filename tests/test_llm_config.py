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


def test_llm_escalation_model_setting_is_a_sonnet_model():
    assert "sonnet" in settings.LLM_ESCALATION_MODEL.lower()


def test_llm_escalation_confidence_threshold_is_configured():
    assert settings.LLM_ESCALATION_CONFIDENCE_THRESHOLD == 0.6


def test_draft_llm_extraction_enabled_defaults_to_false():
    assert settings.DRAFT_LLM_EXTRACTION_ENABLED is False


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


@override_settings(ANTHROPIC_API_KEY="sk-test\n")
def test_get_api_key_strips_trailing_whitespace():
    """A trailing newline in the configured key (e.g. copy/paste into an env
    var) must not be sent to the API — SDK requests with an unstripped key
    fail with a connection error on every call."""
    from core.llm.config import get_api_key

    assert get_api_key() == "sk-test"


@pytest.mark.parametrize(
    "exception_class",
    [LLMConfigurationError, LLMTimeoutError, LLMRequestError, LLMResponseError],
)
def test_llm_exceptions_subclass_llm_error(exception_class):
    assert issubclass(exception_class, LLMError)
