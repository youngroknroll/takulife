"""robots.txt fetch + Disallow evaluation for draft discovery (crawl etiquette).

robots.txt must never be fetched via RobotFileParser.read()/set_url() — that
path is a timeout-less urllib fetch that can hang the process indefinitely
and bypasses the SSRF guard entirely (see prompt_plan.md §2-2). Instead this
module fetches the raw text through the guarded fetch_html core (per-hop SSRF
revalidation, size cap, timeout) and feeds the decoded lines into
RobotFileParser.parse(), which performs no I/O of its own.

Failure policy is fail-closed except for one case: a 404 on robots.txt means
"no rules published" (fail-open, standard robots.txt convention). Every other
failure — 5xx, timeout, connection error, oversized body, SSRF rejection,
unexpected content-type — treats the candidate URL as disallowed so a
transient error can never look like permission to crawl.
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

# robots.txt is conventionally served as text/plain; fetch_html's default
# HTML_CONTENT_TYPES would reject it (replace, not merge — see fetch_html's
# allowed_content_types parameter), so this opts into the narrower type
# instead. Anything else (e.g. an HTML error page) fails closed below.
ROBOTS_TXT_CONTENT_TYPES = ("text/plain",)

# Every fetch failure other than a 404 fails closed (see module docstring).
# OSError covers DNS resolution failures (socket.gaierror) raised by the
# resolver inside validate_fetch_url — without it, a candidate host that
# simply doesn't resolve would crash the caller instead of being treated as
# an ordinary fetch failure. InvalidFetchUrlError covers a candidate URL
# validate_fetch_url rejects outright (unsupported scheme, missing host),
# which fetch_html raises before any network attempt.
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
    """Per-host cached robots.txt checker.

    The cache lives on the instance (self._cache), not the module — a
    module-level cache would leak across unrelated call sites (tests,
    concurrent discovery runs) and never expire. Callers that want caching
    across a run should keep one RobotsChecker instance for that run.
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
        """Crawl-delay (seconds) declared for `url`'s host, from the cached
        parser only — a pure cache read, never a fetch of its own. Returns
        None when the host has not been checked yet (nothing cached), when
        its robots.txt fetch failed (cached as None, see `check()`), or when
        the fetched robots.txt simply did not declare a Crawl-delay for
        USER_AGENT. Callers that want a real value must call `check()` (or
        `is_allowed()`) for the same URL first so the parser is cached."""
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
    """A parser with no rules at all — robots.txt 404 means "allow everything".

    parse() (not read()) also sets last_checked, which can_fetch requires
    before it will return True for an unmatched agent.
    """
    parser = RobotFileParser()
    parser.parse([])
    return parser
