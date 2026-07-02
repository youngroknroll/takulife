"""Domain-agnostic exception hierarchy for the core LLM client adapter.

All errors raised from core.llm normalize to one of these, so callers never
need to catch anthropic SDK exceptions directly.
"""


class LLMError(Exception):
    """Base class for all core.llm errors."""


class LLMConfigurationError(LLMError):
    """Raised when required LLM configuration (e.g. API key) is missing."""


class LLMTimeoutError(LLMError):
    """Raised when a request to the LLM provider times out."""


class LLMRequestError(LLMError):
    """Raised when the LLM provider request fails (connection/5xx errors)."""


class LLMResponseError(LLMError):
    """Raised when the LLM provider response is missing the expected data."""
