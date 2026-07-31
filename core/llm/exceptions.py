"""core LLM 클라이언트 어댑터용 도메인 무관 예외 계층.

core.llm에서 발생하는 모든 오류는 이 중 하나로 정규화되므로, 호출자는
anthropic SDK 예외를 직접 잡을 필요가 없다.
"""


class LLMError(Exception):
    """core.llm 모든 오류의 기반 클래스."""


class LLMConfigurationError(LLMError):
    """필수 LLM 설정(예: API 키)이 없을 때 발생한다."""


class LLMTimeoutError(LLMError):
    """LLM 제공자 요청이 타임아웃될 때 발생한다."""


class LLMRequestError(LLMError):
    """LLM 제공자 요청이 실패할 때(연결/5xx 오류) 발생한다."""


class LLMResponseError(LLMError):
    """LLM 제공자 응답에 기대한 데이터가 없을 때 발생한다."""
