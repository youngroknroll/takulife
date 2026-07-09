import httpx
import socket
from urllib.parse import urljoin

from django.conf import settings

from .url_safety import validate_fetch_url


REQUEST_TIMEOUT_SECONDS = 5.0
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 1_000_000
USER_AGENT = "OshiLifeBot/1.0"
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


class FetchError(Exception):
    pass


class FetchHttpStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class UnsupportedContentTypeError(Exception):
    pass


class ResponseTooLargeError(Exception):
    pass


def _build_user_agent():
    # Read the setting at call time (not module import time) so
    # override_settings takes effect and a deployment can set contact info
    # without a code change.
    contact = settings.DRAFT_FETCH_CONTACT.strip()
    if contact:
        return f"{USER_AGENT} (+{contact})"
    return USER_AGENT


def fetch_html(url, *, allowed_content_types=None):
    """Fetch `url` and return its decoded body, enforcing the SSRF guard,
    a redirect cap, a response-size cap, and a content-type allowlist.

    `allowed_content_types` replaces the default HTML_CONTENT_TYPES entirely
    (it does not merge with it) — pass an explicit tuple to opt into a
    different content type (e.g. robots.txt's text/plain). An empty tuple
    rejects every response, since no prefix will ever match.
    """
    content_types = allowed_content_types if allowed_content_types is not None else HTML_CONTENT_TYPES
    # Validate the initial URL before any client/connection resources are
    # created — a known-unsafe candidate (private IP, unsupported scheme)
    # must not reach httpx.Client at all. The per-hop revalidation inside
    # the loop below still runs for every hop, including this first one;
    # that is the authoritative SSRF gate for redirect targets and must not
    # be removed (see tests/test_draft_fetching_redirect_revalidation.py).
    validate_fetch_url(url, resolver=socket.getaddrinfo)
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            headers={"User-Agent": _build_user_agent()},
        ) as client:
            current_url = url
            for redirect_count in range(MAX_REDIRECTS + 1):
                validate_fetch_url(current_url, resolver=socket.getaddrinfo)
                with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location or redirect_count == MAX_REDIRECTS:
                            raise FetchError
                        current_url = urljoin(current_url, location)
                        continue

                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise FetchHttpStatusError(exc.response.status_code) from exc

                    content_type = (response.headers.get("content-type") or "").lower()
                    if not any(content_type.startswith(prefix) for prefix in content_types):
                        raise UnsupportedContentTypeError

                    chunks = []
                    content_length = 0
                    for chunk in response.iter_bytes():
                        content_length += len(chunk)
                        if content_length > MAX_RESPONSE_BYTES:
                            raise ResponseTooLargeError
                        chunks.append(chunk)

                    return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    except httpx.HTTPError as exc:
        raise FetchError from exc
