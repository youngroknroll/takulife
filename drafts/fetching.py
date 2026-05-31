import httpx


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
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise FetchError from exc

    content_type = (response.headers.get("content-type") or "").lower()
    if not any(content_type.startswith(prefix) for prefix in HTML_CONTENT_TYPES):
        raise UnsupportedContentTypeError

    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ResponseTooLargeError

    return response.text
