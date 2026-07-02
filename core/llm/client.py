"""Thin adapter around the anthropic SDK: client construction + a single
tool-forced call helper. Domain-agnostic — callers (e.g. drafts/) own prompt
content and schema; this module only normalizes transport/config concerns.
"""
import anthropic
from django.conf import settings

from core.llm.config import get_api_key
from core.llm.exceptions import LLMRequestError, LLMResponseError, LLMTimeoutError


def get_client():
    return anthropic.Anthropic(api_key=get_api_key(), timeout=settings.LLM_TIMEOUT_SECONDS)


def call_tool(*, system_prompt, user_content, tool_name, tool_schema, client=None):
    if client is None:
        client = get_client()

    try:
        response = client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            tools=[{"name": tool_name, "input_schema": tool_schema}],
            tool_choice={"type": "tool", "name": tool_name},
        )
    except anthropic.APITimeoutError as error:
        raise LLMTimeoutError("LLM request timed out.") from error
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as error:
        raise LLMRequestError("LLM request failed.") from error

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            return block.input

    raise LLMResponseError("LLM response did not contain a matching tool_use block.")
