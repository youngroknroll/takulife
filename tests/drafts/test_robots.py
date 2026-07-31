"""drafts.robots(robots.txt 페치 + Disallow 판정) 테스트. robots.txt는
RobotFileParser.read()/set_url()로 절대 가져오면 안 된다 — 그 경로는 타임아웃이
없는 urllib 페치라 프로세스가 멈출 수 있고 SSRF 방어를 완전히 우회한다. 대신
drafts.robots는 방어된 fetch_html로 원문을 가져와 I/O 없는
RobotFileParser.parse()에 넘긴다.

TestDecisionLogic은 fetch_html을 직접 모킹해 순수 판정 로직만 검증하고,
TestGuardInheritance는 fetch_html을 실제로 두고 그 아래 계층(httpx.Client,
validate_fetch_url, socket.getaddrinfo)만 패치한다 — SSRF 방어가 실제로
상속되는지(RobotFileParser/urllib을 썼다면 이 패치들이 안 먹혀 테스트가
실패했을 것) 증명하기 위해서다."""
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
        # 판정 로직 자체는 모킹하지 않는다(fetch_html/validate_fetch_url이
        # 실제로 동작). 리터럴 사설 IP는 네트워크 시도 전에 거부돼야 하므로,
        # httpx.Client가 생성되면 바로 실패하게 패치해 "네트워크 미시도"까지
        # 검증한다.
        def _raise_if_called(*args, **kwargs):
            raise AssertionError("network attempted")

        monkeypatch.setattr(fetching.httpx, "Client", _raise_if_called)

        checker = RobotsChecker()
        result = checker.check("http://127.0.0.1/admin")
        assert result == RobotsCheckResult(False, ROBOTS_FETCH_FAILED)

    def test_지원하지_않는_URL_스킴은_예외_없이_차단으로_처리된다(self):
        # 아무것도 모킹하지 않는다: validate_fetch_url이 네트워크 시도 전에
        # 지원하지 않는 스킴을 거부하므로, check()는 예외 대신 차단으로
        # 안전하게 처리해야 한다.
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
        # robots.txt 페치가 실패한 호스트도 실패로 캐시되어 같은 실행 안에서
        # 재조회 시 재요청하지 않는다. 페치 실패는 "규칙 없음"과 달라 후보
        # URL마다 매번 새로 네트워크를 시도하면 안 된다.
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
    """crawl_delay()는 사이트가 자체 Crawl-delay를 공개했을 때 호출자(discover_drafts)가
    기본 INTER_REQUEST_DELAY_SECONDS보다 느리게 조절할 수 있게 한다. 순수 캐시
    읽기이며 자체 페치는 하지 않는다."""

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
        # fetch_html을 전혀 패치하지 않는다: 실제 네트워크 시도가 있으면 이
        # 테스트는 실패한다. 캐시 미스에도 페치하지 않는 순수 캐시 읽기여야
        # 통과한다.
        checker = RobotsChecker()
        assert checker.crawl_delay("https://example.com/page") is None

    def test_robots_txt_가져오기에_실패한_호스트는_crawl_delay가_None이다(self, monkeypatch):
        def _raise(url, **kwargs):
            raise FetchError()

        monkeypatch.setattr(robots, "fetch_html", _raise)

        checker = RobotsChecker()
        checker.check("https://example.com/page")
        assert checker.crawl_delay("https://example.com/page") is None
