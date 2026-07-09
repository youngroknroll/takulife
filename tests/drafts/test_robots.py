"""Tests for drafts.robots — robots.txt fetch + Disallow evaluation.

robots.txt must never be fetched via RobotFileParser.read()/set_url(); that
path is a timeout-less urllib fetch that can hang the process and bypasses
the SSRF guard entirely. Instead drafts.robots fetches the raw text through
the guarded fetch_html core (which re-validates every hop, caps the response
size, and times out) and feeds the decoded lines into
RobotFileParser.parse(), which performs no I/O of its own.

Two mocking styles are used deliberately:
- D group (TestDecisionLogic) mocks drafts.robots.fetch_html directly, to pin
  the pure allow/disallow/404/failure decision logic without touching the
  network layer at all.
- E group (TestGuardInheritance) leaves fetch_html real and instead patches
  the fetching-layer choke points (httpx.Client / validate_fetch_url /
  socket.getaddrinfo) — this is what proves the guard is actually inherited
  rather than bypassed: an implementation using RobotFileParser.read()/urllib
  would not be affected by these patches and would fail these tests.
"""
import socket

import httpx
import pytest
from django.test import override_settings

import drafts.fetching as fetching
import drafts.robots as robots
from drafts.fetching import (
    MAX_RESPONSE_BYTES,
    FetchError,
    FetchHttpStatusError,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
)
from drafts.robots import (
    ROBOTS_DISALLOWED,
    ROBOTS_FETCH_FAILED,
    RobotsChecker,
    RobotsCheckResult,
)
from drafts.url_safety import InvalidFetchUrlError


class TestDecisionLogic:
    def test_is_allowed_true_when_no_disallow_rule_matches(self, monkeypatch):
        monkeypatch.setattr(robots, "fetch_html", lambda url, **kwargs: "User-agent: *\nAllow: /\n")

        checker = RobotsChecker()
        assert checker.is_allowed("https://example.com/page") is True

    def test_is_allowed_false_when_disallow_rule_matches(self, monkeypatch):
        monkeypatch.setattr(
            robots, "fetch_html",
            lambda url, **kwargs: "User-agent: *\nDisallow: /private/\n",
        )

        checker = RobotsChecker()
        assert checker.is_allowed("https://example.com/private/x") is False

    def test_check_reason_is_robots_disallowed_when_rule_matches(self, monkeypatch):
        monkeypatch.setattr(
            robots, "fetch_html",
            lambda url, **kwargs: "User-agent: *\nDisallow: /private/\n",
        )

        checker = RobotsChecker()
        result = checker.check("https://example.com/private/x")
        assert result == RobotsCheckResult(False, ROBOTS_DISALLOWED)

    def test_is_allowed_true_when_robots_txt_returns_404(self, monkeypatch):
        def _raise_404(url, **kwargs):
            raise FetchHttpStatusError(404)

        monkeypatch.setattr(robots, "fetch_html", _raise_404)

        checker = RobotsChecker()
        result = checker.check("https://example.com/page")
        assert result == RobotsCheckResult(True, None)

    @pytest.mark.parametrize(
        "exc",
        [
            FetchHttpStatusError(500),
            FetchError(),
            UnsupportedContentTypeError(),
            ResponseTooLargeError(),
            socket.gaierror("dns fail"),
            InvalidFetchUrlError(),
        ],
    )
    def test_check_reason_is_robots_fetch_failed_for_fetch_failures(self, monkeypatch, exc):
        def _raise(url, **kwargs):
            raise exc

        monkeypatch.setattr(robots, "fetch_html", _raise)

        checker = RobotsChecker()
        result = checker.check("https://example.com/page")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)

    @pytest.mark.parametrize(
        "candidate_url, expected_robots_url",
        [
            ("https://example.com/deep/nested/page?x=1", "https://example.com/robots.txt"),
            ("https://example.com:8443/x", "https://example.com:8443/robots.txt"),
        ],
    )
    def test_is_allowed_requests_robots_txt_at_host_root_not_candidate_path(
        self, monkeypatch, candidate_url, expected_robots_url
    ):
        captured = {}

        def _capture(url, **kwargs):
            captured["url"] = url
            return "User-agent: *\nAllow: /\n"

        monkeypatch.setattr(robots, "fetch_html", _capture)

        RobotsChecker().is_allowed(candidate_url)
        assert captured["url"] == expected_robots_url


class TestGuardInheritance:
    def test_is_allowed_false_when_candidate_host_is_a_private_ip(self, monkeypatch):
        # No mocking of the decision path itself: a literal private-IP
        # candidate must be rejected before any network attempt
        # (fetch_html/validate_fetch_url are real). httpx.Client is patched
        # to blow up if it is ever constructed, so the assertion covers not
        # just the return value but the "no network attempted" guarantee.
        def _raise_if_called(*args, **kwargs):
            raise AssertionError("network attempted")

        monkeypatch.setattr(fetching.httpx, "Client", _raise_if_called)

        checker = RobotsChecker()
        result = checker.check("http://127.0.0.1/admin")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)

    def test_is_allowed_false_when_candidate_url_scheme_is_unsupported(self):
        # No mocking at all: validate_fetch_url rejects an unsupported
        # scheme (InvalidFetchUrlError) before any network attempt, so this
        # must fail closed rather than raise out of check().
        checker = RobotsChecker()
        result = checker.check("ftp://example.com/x")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)

    def test_is_allowed_false_when_robots_txt_response_exceeds_size_cap(self, monkeypatch, install_mock_transport):
        def handler(request):
            body = b"x" * (MAX_RESPONSE_BYTES + 1)
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=body)

        install_mock_transport(monkeypatch, handler)
        monkeypatch.setattr(fetching, "validate_fetch_url", lambda *a, **k: None)

        checker = RobotsChecker()
        result = checker.check("https://example.com/page")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)

    def test_is_allowed_false_when_robots_txt_fetch_times_out(self, monkeypatch, install_mock_transport):
        def handler(request):
            raise httpx.ReadTimeout("timed out", request=request)

        install_mock_transport(monkeypatch, handler)
        monkeypatch.setattr(fetching, "validate_fetch_url", lambda *a, **k: None)

        checker = RobotsChecker()
        result = checker.check("https://example.com/page")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)


@override_settings(DRAFT_FETCH_CONTACT="https://example.com/about")
def test_is_allowed_matches_disallow_rule_for_bare_product_token_even_when_contact_suffix_configured(
    monkeypatch,
):
    monkeypatch.setattr(
        robots, "fetch_html",
        lambda url, **kwargs: "User-agent: TakuLifeBot\nDisallow: /private/\n",
    )

    checker = RobotsChecker()
    assert checker.is_allowed("https://example.com/private/x") is False


class TestPerInstanceCache:
    def test_second_call_for_same_host_does_not_refetch_robots_txt(self, monkeypatch):
        calls = []

        def _fetch(url, **kwargs):
            calls.append(url)
            return "User-agent: *\nAllow: /\n"

        monkeypatch.setattr(robots, "fetch_html", _fetch)

        checker = RobotsChecker()
        checker.is_allowed("https://example.com/a")
        checker.is_allowed("https://example.com/b")
        assert len(calls) == 1

    def test_different_host_triggers_a_second_fetch(self, monkeypatch):
        calls = []

        def _fetch(url, **kwargs):
            calls.append(url)
            return "User-agent: *\nAllow: /\n"

        monkeypatch.setattr(robots, "fetch_html", _fetch)

        checker = RobotsChecker()
        checker.is_allowed("https://example.com/a")
        checker.is_allowed("https://other.example.com/a")
        assert len(calls) == 2

    def test_new_checker_instance_starts_with_an_empty_cache(self, monkeypatch):
        calls = []

        def _fetch(url, **kwargs):
            calls.append(url)
            return "User-agent: *\nAllow: /\n"

        monkeypatch.setattr(robots, "fetch_html", _fetch)

        RobotsChecker().is_allowed("https://example.com/a")
        RobotsChecker().is_allowed("https://example.com/b")
        assert len(calls) == 2

    def test_second_call_after_fetch_failure_does_not_retry(self, monkeypatch):
        # A host whose robots.txt fetch failed is still cached (as a failure)
        # so re-checking it within the same run does not retry the fetch —
        # a fetch_html failure is not "no rules published" and must not
        # trigger a fresh network attempt on every candidate URL.
        calls = []

        def _fetch(url, **kwargs):
            calls.append(url)
            raise FetchError()

        monkeypatch.setattr(robots, "fetch_html", _fetch)

        checker = RobotsChecker()
        checker.is_allowed("https://example.com/a")
        checker.is_allowed("https://example.com/b")
        assert len(calls) == 1


class TestCrawlDelay:
    """crawl_delay() lets the caller (discover_drafts) pace per-host requests
    beyond the flat INTER_REQUEST_DELAY_SECONDS floor when a site publishes
    its own Crawl-delay directive — a pure cache read, never its own fetch."""

    def test_crawl_delay_returns_configured_value_from_cached_robots_txt(self, monkeypatch):
        monkeypatch.setattr(
            robots, "fetch_html",
            lambda url, **kwargs: "User-agent: *\nCrawl-delay: 5\nAllow: /\n",
        )

        checker = RobotsChecker()
        checker.check("https://example.com/page")
        assert checker.crawl_delay("https://example.com/page") == 5

    def test_crawl_delay_is_none_when_robots_txt_has_no_crawl_delay(self, monkeypatch):
        monkeypatch.setattr(
            robots, "fetch_html", lambda url, **kwargs: "User-agent: *\nAllow: /\n"
        )

        checker = RobotsChecker()
        checker.check("https://example.com/page")
        assert checker.crawl_delay("https://example.com/page") is None

    def test_crawl_delay_is_none_when_host_has_not_been_checked_yet(self):
        # No fetch_html patch at all: a real network attempt would blow up
        # this test, so the only way it can pass is a pure cache read that
        # never fetches on a cache miss.
        checker = RobotsChecker()
        assert checker.crawl_delay("https://example.com/page") is None

    def test_crawl_delay_is_none_when_cached_robots_fetch_failed(self, monkeypatch):
        def _raise(url, **kwargs):
            raise FetchError()

        monkeypatch.setattr(robots, "fetch_html", _raise)

        checker = RobotsChecker()
        checker.check("https://example.com/page")
        assert checker.crawl_delay("https://example.com/page") is None
