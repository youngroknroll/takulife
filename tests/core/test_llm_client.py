"""Tests for core.llm.client — all mocked/faked, no real API calls.

Style follows tests/test_draft_fetching.py: dependency injection / monkeypatch
of the anthropic SDK surface, never a live network call.
"""
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from django.test import override_settings

from core.llm.exceptions import (
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError,
    LLMTimeoutError,
)


pytestmark = pytest.mark.unit

TOOL_SCHEMA = {"type": "object", "properties": {"is_event": {"type": "boolean"}}}


def _fake_client(response):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return response

    return SimpleNamespace(messages=SimpleNamespace(create=create)), calls


def _tool_use_response(tool_input, name="extract", stop_reason="tool_use"):
    block = SimpleNamespace(type="tool_use", name=name, input=tool_input)
    return SimpleNamespace(content=[block], stop_reason=stop_reason)


@override_settings(ANTHROPIC_API_KEY="")
def test_api_키_미설정_및_클라이언트_미주입_상태에서_call_tool을_호출하면_설정_오류를_일으킨다(monkeypatch):
    from core.llm import client as client_module

    def _unexpected_client_creation(*args, **kwargs):
        raise AssertionError("must not construct a real anthropic client")

    monkeypatch.setattr(client_module.anthropic, "Anthropic", _unexpected_client_creation)

    with pytest.raises(LLMConfigurationError):
        client_module.call_tool(
            system_prompt="system",
            user_content="user",
            tool_name="extract",
            tool_schema=TOOL_SCHEMA,
        )


def test_call_tool은_tool_use_응답을_받으면_input_딕셔너리를_반환한다():
    from core.llm.client import call_tool

    fake_client, calls = _fake_client(_tool_use_response({"is_event": True}))

    result = call_tool(
        system_prompt="system",
        user_content="user",
        tool_name="extract",
        tool_schema=TOOL_SCHEMA,
        client=fake_client,
    )

    assert result == {"is_event": True}


def test_call_tool은_요청에_tool_choice를_강제하고_tool_schema를_포함한다():
    from core.llm.client import call_tool

    fake_client, calls = _fake_client(_tool_use_response({"is_event": True}))

    call_tool(
        system_prompt="system",
        user_content="user",
        tool_name="extract",
        tool_schema=TOOL_SCHEMA,
        client=fake_client,
    )

    kwargs = calls[0]
    assert kwargs["tool_choice"] == {"type": "tool", "name": "extract"}
    assert any(tool["name"] == "extract" for tool in kwargs["tools"])


@override_settings(LLM_MODEL="claude-haiku-4-5-20251001")
def test_call_tool은_설정된_LLM_MODEL을_요청에_사용한다():
    from core.llm.client import call_tool
    from django.conf import settings

    fake_client, calls = _fake_client(_tool_use_response({"is_event": True}))

    call_tool(
        system_prompt="system",
        user_content="user",
        tool_name="extract",
        tool_schema=TOOL_SCHEMA,
        client=fake_client,
    )

    assert calls[0]["model"] == settings.LLM_MODEL


def test_call_tool은_model_인자가_주어지면_설정값_대신_해당_모델을_사용한다():
    from core.llm.client import call_tool

    fake_client, calls = _fake_client(_tool_use_response({"is_event": True}))

    call_tool(
        system_prompt="system",
        user_content="user",
        tool_name="extract",
        tool_schema=TOOL_SCHEMA,
        model="claude-sonnet-x",
        client=fake_client,
    )

    assert calls[0]["model"] == "claude-sonnet-x"


@override_settings(LLM_MODEL="claude-haiku-4-5-20251001")
def test_call_tool은_model_인자가_없으면_설정된_LLM_MODEL로_폴백한다():
    from core.llm.client import call_tool
    from django.conf import settings

    fake_client, calls = _fake_client(_tool_use_response({"is_event": True}))

    call_tool(
        system_prompt="system",
        user_content="user",
        tool_name="extract",
        tool_schema=TOOL_SCHEMA,
        client=fake_client,
    )

    assert calls[0]["model"] == settings.LLM_MODEL


def test_call_tool은_설정된_LLM_MAX_TOKENS를_요청에_사용한다():
    from core.llm.client import call_tool
    from django.conf import settings

    fake_client, calls = _fake_client(_tool_use_response({"is_event": True}))

    call_tool(
        system_prompt="system",
        user_content="user",
        tool_name="extract",
        tool_schema=TOOL_SCHEMA,
        client=fake_client,
    )

    assert calls[0]["max_tokens"] == settings.LLM_MAX_TOKENS


@pytest.mark.contract
def test_call_tool은_클라이언트가_주입되면_get_api_key를_호출하지_않는다(monkeypatch):
    """Client injection must skip get_api_key entirely — the caller already
    owns the client's credentials. This pins the contract independently of
    whether a local .env happens to have ANTHROPIC_API_KEY set."""
    from core.llm import client as client_module

    def _unexpected_get_api_key():
        raise AssertionError("get_api_key must not be called when client is injected")

    monkeypatch.setattr(client_module, "get_api_key", _unexpected_get_api_key)

    with override_settings(ANTHROPIC_API_KEY=""):
        fake_client, _ = _fake_client(_tool_use_response({"is_event": True}))

        result = client_module.call_tool(
            system_prompt="system",
            user_content="user",
            tool_name="extract",
            tool_schema=TOOL_SCHEMA,
            client=fake_client,
        )

    assert result == {"is_event": True}


def test_call_tool은_tool_use_블록_이름이_일치하지_않으면_응답_오류를_일으킨다():
    from core.llm.client import call_tool

    mismatched_block = SimpleNamespace(type="tool_use", name="other_tool", input={"x": 1})
    response = SimpleNamespace(content=[mismatched_block])
    fake_client, _ = _fake_client(response)

    with pytest.raises(LLMResponseError):
        call_tool(
            system_prompt="system",
            user_content="user",
            tool_name="extract",
            tool_schema=TOOL_SCHEMA,
            client=fake_client,
        )


def test_call_tool은_여러_tool_use_블록_중_이름이_일치하는_블록의_input을_반환한다():
    from core.llm.client import call_tool

    mismatched_block = SimpleNamespace(type="tool_use", name="other_tool", input={"x": 1})
    matching_block = SimpleNamespace(type="tool_use", name="extract", input={"is_event": True})
    response = SimpleNamespace(content=[mismatched_block, matching_block])
    fake_client, _ = _fake_client(response)

    result = call_tool(
        system_prompt="system",
        user_content="user",
        tool_name="extract",
        tool_schema=TOOL_SCHEMA,
        client=fake_client,
    )

    assert result == {"is_event": True}


def test_get_client는_설정된_타임아웃과_api_키로_anthropic_클라이언트를_생성한다(monkeypatch):
    from core.llm import client as client_module
    from django.conf import settings

    captured = {}

    def fake_anthropic(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(client_module.anthropic, "Anthropic", fake_anthropic)

    with override_settings(ANTHROPIC_API_KEY="configured-key"):
        client_module.get_client()

    assert captured["timeout"] == settings.LLM_TIMEOUT_SECONDS
    assert captured["api_key"] == "configured-key"
    assert captured["max_retries"] == 0


def test_call_tool은_max_tokens로_잘린_응답을_받으면_응답_오류를_일으킨다():
    """SDK does not treat hitting max_tokens as an error — tool_use.input can
    be a partial/incomplete dict in that case. A truncated response must not
    be returned to the caller as if it were complete."""
    from core.llm.client import call_tool

    truncated_response = _tool_use_response({"is_event": True}, stop_reason="max_tokens")
    fake_client, _ = _fake_client(truncated_response)

    with pytest.raises(LLMResponseError):
        call_tool(
            system_prompt="system",
            user_content="user",
            tool_name="extract",
            tool_schema=TOOL_SCHEMA,
            client=fake_client,
        )


def test_call_tool은_tool_use_블록이_없으면_응답_오류를_일으킨다():
    from core.llm.client import call_tool

    text_only_response = SimpleNamespace(content=[SimpleNamespace(type="text", text="no tool call")])
    fake_client, _ = _fake_client(text_only_response)

    with pytest.raises(LLMResponseError):
        call_tool(
            system_prompt="system",
            user_content="user",
            tool_name="extract",
            tool_schema=TOOL_SCHEMA,
            client=fake_client,
        )


def test_call_tool은_응답_content가_비어있으면_응답_오류를_일으킨다():
    from core.llm.client import call_tool

    empty_response = SimpleNamespace(content=[])
    fake_client, _ = _fake_client(empty_response)

    with pytest.raises(LLMResponseError):
        call_tool(
            system_prompt="system",
            user_content="user",
            tool_name="extract",
            tool_schema=TOOL_SCHEMA,
            client=fake_client,
        )


def test_call_tool은_api_타임아웃_예외를_LLMTimeoutError로_정규화한다():
    from core.llm.client import call_tool

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def raise_timeout(**kwargs):
        raise anthropic.APITimeoutError(request=request)

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=raise_timeout))

    with pytest.raises(LLMTimeoutError):
        call_tool(
            system_prompt="system",
            user_content="user",
            tool_name="extract",
            tool_schema=TOOL_SCHEMA,
            client=fake_client,
        )


def _make_connection_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(request=request)


def _make_internal_server_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(500, request=request)
    return anthropic.InternalServerError("server error", response=response, body=None)


def _make_response_validation_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(200, request=request)
    return anthropic.APIResponseValidationError(response=response, body=None)


@pytest.mark.parametrize(
    "build_error",
    [_make_connection_error, _make_internal_server_error, _make_response_validation_error],
    ids=["연결_오류", "내부_서버_오류", "응답_검증_오류"],
)
def test_call_tool은_연결_오류와_서버_오류를_LLMRequestError로_정규화한다(build_error):
    from core.llm.client import call_tool

    error = build_error()

    def raise_error(**kwargs):
        raise error

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=raise_error))

    with pytest.raises(LLMRequestError):
        call_tool(
            system_prompt="system",
            user_content="user",
            tool_name="extract",
            tool_schema=TOOL_SCHEMA,
            client=fake_client,
        )
