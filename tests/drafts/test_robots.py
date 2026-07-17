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

pytestmark = pytest.mark.contract


class TestDecisionLogic:
    def test_disallow_규칙이_없으면_허용으로_판단한다(self, monkeypatch):
        monkeypatch.setattr(robots, "fetch_html", lambda url, **kwargs: "User-agent: *\nAllow: /\n")

        checker = RobotsChecker()
        assert checker.is_allowed("https://example.com/page") is True

    def test_disallow_규칙에_일치하면_차단으로_판단한다(self, monkeypatch):
        monkeypatch.setattr(
            robots, "fetch_html",
            lambda url, **kwargs: "User-agent: *\nDisallow: /private/\n",
        )

        checker = RobotsChecker()
        assert checker.is_allowed("https://example.com/private/x") is False

    def test_disallow_규칙에_일치하면_차단_사유가_robots_disallowed로_기록된다(self, monkeypatch):
        monkeypatch.setattr(
            robots, "fetch_html",
            lambda url, **kwargs: "User-agent: *\nDisallow: /private/\n",
        )

        checker = RobotsChecker()
        result = checker.check("https://example.com/private/x")
        assert result == RobotsCheckResult(False, ROBOTS_DISALLOWED)

    def test_robots_txt가_404면_규칙_없음으로_간주해_허용한다(self, monkeypatch):
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
        ids=[
            "HTTP_500_오류",
            "일반_fetch_오류",
            "지원하지_않는_콘텐츠_타입",
            "응답_크기_초과",
            "DNS_조회_실패",
            "유효하지_않은_URL",
        ],
    )
    def test_robots_txt_가져오기가_실패하면_사유를_fetch_failed로_기록하고_차단한다(self, monkeypatch, exc):
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
        ids=["깊은_경로와_쿼리스트링", "비표준_포트"],
    )
    def test_robots_txt는_후보_URL의_경로가_아니라_호스트_루트에서_요청한다(
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
    def test_후보_호스트가_비공개_IP면_네트워크_시도_없이_차단한다(self, monkeypatch):
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

    def test_지원하지_않는_URL_스킴은_예외_없이_차단으로_처리된다(self):
        # No mocking at all: validate_fetch_url rejects an unsupported
        # scheme (InvalidFetchUrlError) before any network attempt, so this
        # must fail closed rather than raise out of check().
        checker = RobotsChecker()
        result = checker.check("ftp://example.com/x")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)

    def test_robots_txt_응답이_크기_상한을_넘으면_차단한다(self, monkeypatch, install_mock_transport):
        def handler(request):
            body = b"x" * (MAX_RESPONSE_BYTES + 1)
            return httpx.Response(200, headers={"content-type": "text/plain"}, content=body)

        install_mock_transport(monkeypatch, handler)
        monkeypatch.setattr(fetching, "validate_fetch_url", lambda *a, **k: None)

        checker = RobotsChecker()
        result = checker.check("https://example.com/page")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)

    def test_robots_txt_요청이_타임아웃되면_차단한다(self, monkeypatch, install_mock_transport):
        def handler(request):
            raise httpx.ReadTimeout("timed out", request=request)

        install_mock_transport(monkeypatch, handler)
        monkeypatch.setattr(fetching, "validate_fetch_url", lambda *a, **k: None)

        checker = RobotsChecker()
        result = checker.check("https://example.com/page")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)


@override_settings(DRAFT_FETCH_CONTACT="https://example.com/about")
def test_연락처_설정이_있어도_순수_제품_토큰만으로_disallow_규칙이_일치한다(
    monkeypatch,
):
    monkeypatch.setattr(
        robots, "fetch_html",
        lambda url, **kwargs: "User-agent: TakuLifeBot\nDisallow: /private/\n",
    )

    checker = RobotsChecker()
    assert checker.is_allowed("https://example.com/private/x") is False


class TestPerInstanceCache:
    def test_같은_호스트를_다시_조회하면_robots_txt를_재요청하지_않는다(self, monkeypatch):
        calls = []

        def _fetch(url, **kwargs):
            calls.append(url)
            return "User-agent: *\nAllow: /\n"

        monkeypatch.setattr(robots, "fetch_html", _fetch)

        checker = RobotsChecker()
        checker.is_allowed("https://example.com/a")
        checker.is_allowed("https://example.com/b")
        assert len(calls) == 1

    def test_다른_호스트를_조회하면_robots_txt를_새로_요청한다(self, monkeypatch):
        calls = []

        def _fetch(url, **kwargs):
            calls.append(url)
            return "User-agent: *\nAllow: /\n"

        monkeypatch.setattr(robots, "fetch_html", _fetch)

        checker = RobotsChecker()
        checker.is_allowed("https://example.com/a")
        checker.is_allowed("https://other.example.com/a")
        assert len(calls) == 2

    def test_새_RobotsChecker_인스턴스는_빈_캐시로_시작한다(self, monkeypatch):
        calls = []

        def _fetch(url, **kwargs):
            calls.append(url)
            return "User-agent: *\nAllow: /\n"

        monkeypatch.setattr(robots, "fetch_html", _fetch)

        RobotsChecker().is_allowed("https://example.com/a")
        RobotsChecker().is_allowed("https://example.com/b")
        assert len(calls) == 2

    def test_가져오기_실패도_캐시되어_재요청하지_않는다(self, monkeypatch):
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

    def test_robots_txt에_crawl_delay가_설정되어_있으면_그_값을_반환한다(self, monkeypatch):
        monkeypatch.setattr(
            robots, "fetch_html",
            lambda url, **kwargs: "User-agent: *\nCrawl-delay: 5\nAllow: /\n",
        )

        checker = RobotsChecker()
        checker.check("https://example.com/page")
        assert checker.crawl_delay("https://example.com/page") == 5

    def test_robots_txt에_crawl_delay가_없으면_None을_반환한다(self, monkeypatch):
        monkeypatch.setattr(
            robots, "fetch_html", lambda url, **kwargs: "User-agent: *\nAllow: /\n"
        )

        checker = RobotsChecker()
        checker.check("https://example.com/page")
        assert checker.crawl_delay("https://example.com/page") is None

    def test_아직_확인하지_않은_호스트는_새_요청_없이_None을_반환한다(self):
        # No fetch_html patch at all: a real network attempt would blow up
        # this test, so the only way it can pass is a pure cache read that
        # never fetches on a cache miss.
        checker = RobotsChecker()
        assert checker.crawl_delay("https://example.com/page") is None

    def test_robots_txt_가져오기에_실패한_호스트는_crawl_delay가_None이다(self, monkeypatch):
        def _raise(url, **kwargs):
            raise FetchError()

        monkeypatch.setattr(robots, "fetch_html", _raise)

        checker = RobotsChecker()
        checker.check("https://example.com/page")
        assert checker.crawl_delay("https://example.com/page") is None
