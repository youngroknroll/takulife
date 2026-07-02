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


TOOL_SCHEMA = {"type": "object", "properties": {"is_event": {"type": "boolean"}}}


def _fake_client(response):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return response

    return SimpleNamespace(messages=SimpleNamespace(create=create)), calls


def _tool_use_response(tool_input, name="extract"):
    block = SimpleNamespace(type="tool_use", name=name, input=tool_input)
    return SimpleNamespace(content=[block])


@override_settings(ANTHROPIC_API_KEY="")
def test_call_tool_without_configured_key_or_injected_client_raises_configuration_error(monkeypatch):
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


def test_call_tool_returns_tool_use_input_dict():
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


def test_call_tool_forces_tool_choice_and_includes_tool_schema():
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
def test_call_tool_uses_configured_model():
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


def test_call_tool_uses_configured_max_tokens():
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


def test_call_tool_with_injected_client_does_not_call_get_api_key(monkeypatch):
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


def test_call_tool_skips_tool_use_block_with_mismatched_name_and_raises_response_error():
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


def test_call_tool_returns_input_from_matching_named_block_among_mismatched_blocks():
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


def test_get_client_constructs_anthropic_client_with_configured_timeout(monkeypatch):
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


def test_call_tool_raises_response_error_when_no_tool_use_block():
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


def test_call_tool_raises_response_error_when_content_is_empty():
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


def test_call_tool_normalizes_api_timeout_error():
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


@pytest.mark.parametrize("build_error", [_make_connection_error, _make_internal_server_error])
def test_call_tool_normalizes_connection_and_server_errors_to_request_error(build_error):
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
