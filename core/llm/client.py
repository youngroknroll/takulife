"""anthropic SDK를 감싸는 얇은 어댑터: 클라이언트 생성 + 도구 강제 호출
도우미 하나. 도메인과 무관하다 — 호출자(예: drafts/)가 프롬프트 내용과
스키마를 소유하고, 이 모듈은 전송/설정 관련 사항만 정리한다.
"""
import anthropic
from django.conf import settings

from core.llm.config import get_api_key
from core.llm.exceptions import LLMRequestError, LLMResponseError, LLMTimeoutError


def get_client():
    # max_retries=0: SDK 기본값(2)을 쓰면 시도마다 LLM_TIMEOUT_SECONDS가
    # 곱해져서, 호출부에 명시한 10초 상한이 조용히 깨진다.
    return anthropic.Anthropic(
        api_key=get_api_key(), timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=0
    )


def call_tool(*, system_prompt, user_content, tool_name, tool_schema, model=None, client=None):
    if client is None:
        client = get_client()

    try:
        response = client.messages.create(
            model=model or settings.LLM_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            tools=[{"name": tool_name, "input_schema": tool_schema}],
            tool_choice={"type": "tool", "name": tool_name},
        )
    except anthropic.APITimeoutError as error:
        raise LLMTimeoutError("LLM request timed out.") from error
    except anthropic.APIError as error:
        raise LLMRequestError("LLM request failed.") from error

    # SDK는 max_tokens 상한에 도달한 것을 오류로 취급하지 않는다 — 잘린
    # tool_use.input도 겉으로는 유효한 JSON처럼 보일 수 있다. 호출자가
    # 조용히 불완전한 데이터를 받지 않도록 여기서 명시적으로 거부한다.
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise LLMResponseError("LLM output truncated (max_tokens); tool input may be incomplete.")

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            return block.input

    raise LLMResponseError("LLM response did not contain a matching tool_use block.")
