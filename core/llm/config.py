from django.conf import settings

from core.llm.exceptions import LLMConfigurationError


def get_api_key():
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key.strip():
        raise LLMConfigurationError("ANTHROPIC_API_KEY is not configured.")
    return api_key.strip()
