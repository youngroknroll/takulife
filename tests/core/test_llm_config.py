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
    """값이 .env가 아니라 프로세스 환경 변수에서 오면 settings가 _get_env의
    strip을 거치지 않고 그대로 읽으므로, 공백만 있는 키도 빈 값과 똑같이
    취급해야 한다."""
    from core.llm.config import get_api_key

    with pytest.raises(LLMConfigurationError):
        get_api_key()


@override_settings(ANTHROPIC_API_KEY="sk-test\n")
def test_get_api_key는_api_키_끝의_공백을_제거하고_반환한다():
    """설정된 키 끝의 줄바꿈(예: 환경 변수에 복사-붙여넣기하며 딸려온 것)이
    그대로 API로 전송되면 안 된다 — 다듬지 않은 키로 보낸 SDK 요청은 매번
    연결 오류로 실패한다."""
    from core.llm.config import get_api_key

    assert get_api_key() == "sk-test"


@pytest.mark.parametrize(
    "exception_class",
    [LLMConfigurationError, LLMTimeoutError, LLMRequestError, LLMResponseError],
    ids=["LLMConfigurationError", "LLMTimeoutError", "LLMRequestError", "LLMResponseError"],
)
def test_llm_예외_클래스들은_LLMError를_상속한다(exception_class):
    assert issubclass(exception_class, LLMError)
