import httpx
import socket
from urllib.parse import urljoin

from django.conf import settings

from .url_safety import validate_fetch_url


REQUEST_TIMEOUT_SECONDS = 5.0
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 1_000_000
USER_AGENT = "TakuLifeBot/1.0"
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
    # 설정을 임포트 시점이 아니라 호출 시점에 읽어야 override_settings가 먹히고,
    # 배포 시 코드 수정 없이 연락처를 바꿀 수 있다.
    contact = settings.DRAFT_FETCH_CONTACT.strip()
    if contact:
        return f"{USER_AGENT} (+{contact})"
    return USER_AGENT


def fetch_html(url, *, allowed_content_types=None):
    """url을 가져와 디코딩된 본문을 반환한다. SSRF 방지, 리다이렉트 횟수 제한, 응답 크기
    제한, content-type 허용 목록을 모두 강제한다.

    allowed_content_types는 기본값 HTML_CONTENT_TYPES를 병합이 아니라 통째로
    대체한다 — robots.txt의 text/plain처럼 다른 타입을 허용하려면 명시적으로 튜플을
    넘겨라. 빈 튜플을 넘기면 어떤 접두어와도 매치되지 않아 모든 응답이 거부된다.
    """
    content_types = allowed_content_types if allowed_content_types is not None else HTML_CONTENT_TYPES
    # 클라이언트를 만들기 전에 최초 URL부터 검증한다 — 사설 IP나 지원하지 않는
    # 스킴처럼 이미 위험한 주소는 httpx.Client에 닿아서도 안 된다. 아래 루프의 매 홉
    # 재검증이 리다이렉트 대상에 대한 실질적 SSRF 방어선이므로 지우면 안 된다
    # (tests/test_draft_fetching_redirect_revalidation.py 참고).
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
