"""Tests for drafts.fetching.fetch_html using an httpx MockTransport.

Covers the redirect cap, content-type rejection, response-size cap, and the
successful decode path without hitting the network. validate_fetch_url is
stubbed here (it has its own dedicated tests) so these focus on fetch behavior.
"""
import httpx
import pytest
from django.test import override_settings

import drafts.fetching as fetching
from drafts.fetching import (
    MAX_RESPONSE_BYTES,
    USER_AGENT,
    FetchError,
    FetchHttpStatusError,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
    fetch_html,
)


def _install(monkeypatch, handler):
    monkeypatch.setattr(fetching, "validate_fetch_url", lambda *a, **k: None)
    real_client = httpx.Client

    def factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(fetching.httpx, "Client", factory)


def test_success_returns_decoded_html(monkeypatch):
    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "text/html; charset=utf-8"},
            content="<html>본문</html>".encode("utf-8"),
        )

    _install(monkeypatch, handler)
    assert "본문" in fetch_html("https://example.com/")


def test_non_html_content_type_rejected(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/json"}, content=b"{}")

    _install(monkeypatch, handler)
    with pytest.raises(UnsupportedContentTypeError):
        fetch_html("https://example.com/data")


def test_response_too_large_rejected(monkeypatch):
    def handler(request):
        body = b"x" * (MAX_RESPONSE_BYTES + 1)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=body)

    _install(monkeypatch, handler)
    with pytest.raises(ResponseTooLargeError):
        fetch_html("https://example.com/big")


def test_too_many_redirects_raises_fetch_error(monkeypatch):
    def handler(request):
        return httpx.Response(302, headers={"location": "https://example.com/next"})

    _install(monkeypatch, handler)
    with pytest.raises(FetchError):
        fetch_html("https://example.com/loop")


def test_transport_http_error_maps_to_fetch_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    _install(monkeypatch, handler)
    with pytest.raises(FetchError):
        fetch_html("https://example.com/down")


def test_fetch_html_accepts_opted_in_xml_content_type(monkeypatch):
    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "application/rss+xml"}, content=b"<rss></rss>"
        )

    _install(monkeypatch, handler)
    result = fetch_html(
        "https://example.com/feed.xml", allowed_content_types=("application/rss+xml",)
    )
    assert result == "<rss></rss>"


def test_fetch_html_opted_in_content_types_replace_default_not_merge(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    _install(monkeypatch, handler)
    with pytest.raises(UnsupportedContentTypeError):
        fetch_html("https://example.com/feed.xml", allowed_content_types=("application/rss+xml",))


@pytest.mark.parametrize("status", [404, 500])
def test_fetch_html_raises_status_error_with_code_for_http_error_responses(monkeypatch, status):
    def handler(request):
        return httpx.Response(status, headers={"content-type": "text/html"}, content=b"")

    _install(monkeypatch, handler)
    with pytest.raises(FetchHttpStatusError) as exc_info:
        fetch_html("https://example.com/missing")

    assert exc_info.value.status_code == status


def test_fetch_html_response_too_large_enforced_with_xml_content_type(monkeypatch):
    def handler(request):
        body = b"x" * (MAX_RESPONSE_BYTES + 1)
        return httpx.Response(200, headers={"content-type": "application/rss+xml"}, content=body)

    _install(monkeypatch, handler)
    with pytest.raises(ResponseTooLargeError):
        fetch_html("https://example.com/feed.xml", allowed_content_types=("application/rss+xml",))


def test_fetch_html_user_agent_defaults_to_current_value_when_contact_unset(monkeypatch):
    captured = {}

    def handler(request):
        captured["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    _install(monkeypatch, handler)
    fetch_html("https://example.com/")
    assert captured["user_agent"] == USER_AGENT


@override_settings(DRAFT_FETCH_CONTACT="https://example.com/about")
def test_fetch_html_user_agent_appends_contact_when_settings_configured(monkeypatch):
    captured = {}

    def handler(request):
        captured["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    _install(monkeypatch, handler)
    fetch_html("https://example.com/")
    assert captured["user_agent"] == "OshiLogBot/1.0 (+https://example.com/about)"


@override_settings(DRAFT_FETCH_CONTACT="https://example.com/about\n")
def test_fetch_html_user_agent_strips_trailing_whitespace_from_contact(monkeypatch):
    # Defends against a trailing newline left in a .env value (a common
    # copy/paste mistake) leaking into the User-Agent header.
    captured = {}

    def handler(request):
        captured["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    _install(monkeypatch, handler)
    fetch_html("https://example.com/")
    assert captured["user_agent"] == "OshiLogBot/1.0 (+https://example.com/about)"
