"""Tests for drafts.fetching.fetch_html using an httpx MockTransport.

Covers the redirect cap, content-type rejection, response-size cap, and the
successful decode path without hitting the network. validate_fetch_url is
stubbed here (it has its own dedicated tests) so these focus on fetch behavior.
"""
import httpx
import pytest

import drafts.fetching as fetching
from drafts.fetching import (
    MAX_RESPONSE_BYTES,
    FetchError,
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
