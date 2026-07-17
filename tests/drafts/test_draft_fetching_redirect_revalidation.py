"""Regression lock: fetch_html re-validates the SSRF guard on every redirect
hop, not just the initial URL.

This is the "per-hop resolver revalidation" safety property from
prompt_plan.md §2-3 — the authoritative SSRF gate now that IP pinning is out
of scope for PR-1 (httpx has no public DNS hook to pin against). Unlike
tests/test_draft_fetching.py's `install_mock_transport(..., stub_validate_fetch_url=True)`
usage (which stubs validate_fetch_url away entirely so those tests can focus
on fetch mechanics), these tests deliberately exercise validate_fetch_url's
real logic on the redirect target so a regression that skips revalidation on
later hops would be caught.

These are not red/green tests — they must already pass against the baseline
fetching.py (the per-hop call was already there) and must still pass after
the allowed_content_types/FetchHttpStatusError/UA changes land.
"""
import httpx
import pytest

import drafts.fetching as fetching
from drafts.fetching import fetch_html
from drafts.url_safety import UnsafeFetchUrlError, validate_fetch_url


pytestmark = pytest.mark.contract


def test_리다이렉트_대상이_사설_IP_리터럴이면_거부된다(monkeypatch, install_mock_transport):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    install_mock_transport(monkeypatch, handler)
    # Drop the resolver kwarg only (same technique as
    # tests/test_drafts_services.py:187-190): the literal-IP branch of
    # validate_fetch_url needs no DNS resolution anyway.
    monkeypatch.setattr(
        fetching, "validate_fetch_url", lambda url, **kwargs: validate_fetch_url(url)
    )

    with pytest.raises(UnsafeFetchUrlError):
        fetch_html("https://example.com/")

    assert len(calls) == 1


def test_리다이렉트_대상_호스트명이_사설_IP로_해석되면_거부된다(
    monkeypatch, install_mock_transport, fake_resolver
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://evil.example.com/"})

    install_mock_transport(monkeypatch, handler)
    resolver = fake_resolver({"example.com": "93.184.216.34", "evil.example.com": "10.1.2.3"})
    monkeypatch.setattr(fetching.socket, "getaddrinfo", resolver)

    with pytest.raises(UnsafeFetchUrlError):
        fetch_html("https://example.com/")

    assert len(calls) == 1
