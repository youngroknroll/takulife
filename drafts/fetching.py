import httpx
import socket
from urllib.parse import urljoin

from .url_safety import validate_fetch_url


REQUEST_TIMEOUT_SECONDS = 5.0
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 1_000_000
USER_AGENT = "OshiLogBot/1.0"
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


class FetchError(Exception):
    pass


class UnsupportedContentTypeError(Exception):
    pass


class ResponseTooLargeError(Exception):
    pass


def fetch_html(url):
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            headers={"User-Agent": USER_AGENT},
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

                    response.raise_for_status()
                    content_type = (response.headers.get("content-type") or "").lower()
                    if not any(content_type.startswith(prefix) for prefix in HTML_CONTENT_TYPES):
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
