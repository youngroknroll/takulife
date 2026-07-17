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


pytestmark = pytest.mark.unit


def test_llm_model_설정값은_haiku_모델이다():
    assert "haiku" in settings.LLM_MODEL.lower()


def test_llm_timeout_seconds_설정값은_10초다():
    assert settings.LLM_TIMEOUT_SECONDS == 10


def test_llm_escalation_model_설정값은_sonnet_모델이다():
    assert "sonnet" in settings.LLM_ESCALATION_MODEL.lower()


def test_llm_escalation_confidence_threshold_설정값은_0_6이다():
    assert settings.LLM_ESCALATION_CONFIDENCE_THRESHOLD == 0.6


def test_draft_llm_extraction_enabled_설정값은_기본으로_false다():
    assert settings.DRAFT_LLM_EXTRACTION_ENABLED is False


@override_settings(ANTHROPIC_API_KEY="")
def test_get_api_key는_api_키가_빈_문자열이면_설정_오류를_일으킨다():
    from core.llm.config import get_api_key

    with pytest.raises(LLMConfigurationError):
        get_api_key()


@override_settings(ANTHROPIC_API_KEY="configured-key")
def test_get_api_key는_설정된_api_키_값을_반환한다():
    from core.llm.config import get_api_key

    assert get_api_key() == "configured-key"


@override_settings(ANTHROPIC_API_KEY="   ")
def test_get_api_key는_api_키가_공백만_있으면_설정_오류를_일으킨다():
    """OS env vars are read directly by settings (bypassing _get_env's strip
    when the value comes from the process environment rather than .env), so a
    whitespace-only key must be treated the same as blank."""
    from core.llm.config import get_api_key

    with pytest.raises(LLMConfigurationError):
        get_api_key()


@override_settings(ANTHROPIC_API_KEY="sk-test\n")
def test_get_api_key는_api_키_끝의_공백을_제거하고_반환한다():
    """A trailing newline in the configured key (e.g. copy/paste into an env
    var) must not be sent to the API — SDK requests with an unstripped key
    fail with a connection error on every call."""
    from core.llm.config import get_api_key

    assert get_api_key() == "sk-test"


@pytest.mark.parametrize(
    "exception_class",
    [LLMConfigurationError, LLMTimeoutError, LLMRequestError, LLMResponseError],
    ids=["LLMConfigurationError", "LLMTimeoutError", "LLMRequestError", "LLMResponseError"],
)
def test_llm_예외_클래스들은_LLMError를_상속한다(exception_class):
    assert issubclass(exception_class, LLMError)
