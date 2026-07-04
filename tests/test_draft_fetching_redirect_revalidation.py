"""Regression lock: fetch_html re-validates the SSRF guard on every redirect
hop, not just the initial URL.

This is the "per-hop resolver revalidation" safety property from
prompt_plan.md §2-3 — the authoritative SSRF gate now that IP pinning is out
of scope for PR-1 (httpx has no public DNS hook to pin against). Unlike
tests/test_draft_fetching.py's `_install` helper (which stubs
validate_fetch_url away entirely so those tests can focus on fetch mechanics),
these tests deliberately exercise validate_fetch_url's real logic on the
redirect target so a regression that skips revalidation on later hops would
be caught.

These are not red/green tests — they must already pass against the baseline
fetching.py (the per-hop call was already there) and must still pass after
the allowed_content_types/FetchHttpStatusError/UA changes land.
"""
import socket

import httpx
import pytest

import drafts.fetching as fetching
from drafts.fetching import fetch_html
from drafts.url_safety import UnsafeFetchUrlError, validate_fetch_url


def _install_transport(monkeypatch, handler):
    real_client = httpx.Client

    def factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(fetching.httpx, "Client", factory)


def _resolver_for(ip_by_host, port=443):
    def _resolve(host, _port, *, type=None):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip_by_host[host], port))]

    return _resolve


def test_redirect_to_private_ip_literal_is_rejected(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    _install_transport(monkeypatch, handler)
    # Drop the resolver kwarg only (same technique as
    # tests/test_drafts_services.py:187-190): the literal-IP branch of
    # validate_fetch_url needs no DNS resolution anyway.
    monkeypatch.setattr(
        fetching, "validate_fetch_url", lambda url, **kwargs: validate_fetch_url(url)
    )

    with pytest.raises(UnsafeFetchUrlError):
        fetch_html("https://example.com/")

    assert len(calls) == 1


def test_redirect_to_hostname_resolving_to_private_ip_is_rejected(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://evil.example.com/"})

    _install_transport(monkeypatch, handler)
    resolver = _resolver_for({"example.com": "93.184.216.34", "evil.example.com": "10.1.2.3"})
    monkeypatch.setattr(fetching.socket, "getaddrinfo", resolver)

    with pytest.raises(UnsafeFetchUrlError):
        fetch_html("https://example.com/")

    assert len(calls) == 1
