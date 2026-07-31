"""드래프트 수집의 robots.txt 크롤링 예절 처리.

robots.txt는 RobotFileParser.read()/set_url()로 절대 받아오면 안 된다 — 그 경로는
타임아웃이 없는 urllib 요청이라 무한정 멈출 수 있고 SSRF 방어도 완전히 우회한다.
대신 이 모듈은 SSRF 재검증·크기 제한·타임아웃이 걸린 fetch_html로 원문을 가져온 뒤
RobotFileParser.parse()에 줄 단위로 넘긴다(parse 자체는 I/O를 하지 않는다).

기본은 실패 시 차단(fail-closed)이지만 예외가 하나 있다: robots.txt가 404면
"규칙 없음"으로 보고 허용한다(표준 관례). 그 외 모든 실패(5xx, 타임아웃, 연결 오류,
크기 초과, SSRF 거부, 예상 밖 content-type)는 후보 URL을 차단 처리한다 — 일시 오류가
크롤링 허가로 오인되면 안 된다.
"""
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from .fetching import (
    USER_AGENT,
    FetchError,
    FetchHttpStatusError,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
    fetch_html,
)
from .url_safety import InvalidFetchUrlError, UnsafeFetchUrlError


ROBOTS_DISALLOWED = "robots_disallowed"
ROBOTS_FETCH_FAILED = "robots_fetch_failed"

# robots.txt는 관례상 text/plain으로 오므로 fetch_html 기본 HTML_CONTENT_TYPES로는
# 거부된다 — allowed_content_types는 병합이 아니라 대체이므로 이 타입만 따로
# 허용한다. 그 외(예: HTML 오류 페이지)는 아래에서 차단된다.
ROBOTS_TXT_CONTENT_TYPES = ("text/plain",)

# 404 이외의 모든 실패는 차단 처리한다(모듈 설명 참고). OSError는
# validate_fetch_url 내부 리졸버가 내는 DNS 조회 실패(socket.gaierror)까지
# 포함한다 — 없으면 이름이 안 풀리는 호스트가 호출자를 그대로 죽여버린다.
# InvalidFetchUrlError는 validate_fetch_url이 애초에 거부하는 URL(지원하지 않는
# 스킴, 호스트 없음)이며 fetch_html이 네트워크 시도 전에 던진다.
_ROBOTS_FETCH_FAILURES = (
    FetchError,
    UnsupportedContentTypeError,
    ResponseTooLargeError,
    UnsafeFetchUrlError,
    InvalidFetchUrlError,
    OSError,
)


@dataclass(frozen=True)
class RobotsCheckResult:
    allowed: bool
    reason: str = None


class RobotsChecker:
    """호스트별로 robots.txt를 캐시하는 체커.

    캐시는 모듈이 아니라 인스턴스(self._cache)에 둔다 — 모듈 전역 캐시는 테스트나
    동시 수집 실행 사이에 서로 새어나가고 절대 만료되지 않는다. 실행 한 번 동안
    캐시를 쓰려면 호출자가 RobotsChecker 인스턴스 하나를 계속 들고 있어야 한다.
    """

    def __init__(self):
        self._cache = {}

    def check(self, url):
        parsed = urlsplit(url)
        host_key = (parsed.scheme, parsed.netloc)
        if host_key not in self._cache:
            self._cache[host_key] = self._fetch_parser(parsed)
        parser = self._cache[host_key]

        if parser is None:
            return RobotsCheckResult(False, ROBOTS_FETCH_FAILED)
        if parser.can_fetch(USER_AGENT, url):
            return RobotsCheckResult(True, None)
        return RobotsCheckResult(False, ROBOTS_DISALLOWED)

    def is_allowed(self, url):
        return self.check(url).allowed

    def crawl_delay(self, url):
        """url의 호스트에 대해 캐시된 파서에서만 Crawl-delay(초)를 읽는다 — 직접
        fetch하지 않는 순수 캐시 조회다. 아직 확인 전(캐시 없음), robots.txt fetch
        실패(check()에서 None으로 캐시됨), 또는 robots.txt에 USER_AGENT용
        Crawl-delay가 없는 경우 모두 None을 반환한다. 실제 값을 받으려면 먼저 같은
        URL로 check()나 is_allowed()를 호출해 파서를 캐시해둬야 한다."""
        parsed = urlsplit(url)
        host_key = (parsed.scheme, parsed.netloc)
        parser = self._cache.get(host_key)
        if parser is None:
            return None
        return parser.crawl_delay(USER_AGENT)

    def _fetch_parser(self, parsed):
        robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
        try:
            body = fetch_html(robots_url, allowed_content_types=ROBOTS_TXT_CONTENT_TYPES)
        except FetchHttpStatusError as exc:
            if exc.status_code == 404:
                return _empty_ruleset()
            return None
        except _ROBOTS_FETCH_FAILURES:
            return None

        parser = RobotFileParser()
        parser.parse(body.splitlines())
        return parser


def _empty_ruleset():
    """규칙이 하나도 없는 파서 — robots.txt가 404면 "전부 허용"으로 취급한다.

    read()가 아니라 parse()를 써야 last_checked도 같이 설정되는데, can_fetch가
    매치되지 않는 에이전트에 True를 돌려주려면 이 값이 필요하다.
    """
    parser = RobotFileParser()
    parser.parse([])
    return parser
