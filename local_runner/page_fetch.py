"""이벤트 URL을 실제로 읽어오는 결정론적 읽기 단계다. 모델을 쓰지 않는다 —
호스트만 보고 인스타·X 캡션 경로와 일반 웹 경로 중 하나로 그대로 분기한다."""
import socket
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from local_runner.url_safety import validate_fetch_url

# 계정형(캡션) 호스트 집합. 서버(drafts.discovery.SNS_HOSTNAMES)와 같은 목록이
# 여기 다시 나온다 — 러너는 Django·서버 도메인 모듈을 임포트할 수 없어 공유가
# 불가능하다. 서버 쪽 목록이 바뀌면 이쪽도 같이 손봐야 한다.
_CAPTION_HOSTNAMES = {
    "instagram.com",
    "www.instagram.com",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
}

_GENERAL_WEB_TIMEOUT_SECONDS = 15
# 서버 fetching.py의 MAX_RESPONSE_BYTES와 같은 값이다(같은 이유로 상한을 둔다).
_GENERAL_WEB_MAX_RESPONSE_BYTES = 1_000_000
# 인스타 경로와 달리 일반 웹은 브라우저 UA를 쓴다 — 호스트별로 UA 요구가
# 갈린다는 실측(2026-09-11)에 따른 것이다.
_GENERAL_WEB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class ResponseTooLargeError(Exception):
    pass


class EmptyExtractionError(Exception):
    pass


def _fetch_instagram_caption(url):
    # 다음 사이클: 인스타/X 게시물 페이지를 httpx로 가져와 캡션만 분리한다.
    pass


def _parse_raw_fields(html):
    # 서버 판정(drafts/extraction.py의 parse_raw_fields)의 복제본이다. 러너는
    # 서버 도메인 모듈을 임포트할 수 없어 공유가 불가능하다. 원본 경로:
    # drafts/extraction.py:78-97 — 우선순위를 바꿀 때는 두 파일을 함께 고쳐야
    # 한다.
    soup = BeautifulSoup(html, "html.parser")

    og_title = soup.find("meta", attrs={"property": "og:title"})
    title_tag = soup.find("title")
    meta_description = soup.find("meta", attrs={"name": "description"})

    raw_title = (
        (og_title.get("content") if og_title else None)
        or (title_tag.get_text(strip=True) if title_tag else "")
    ).strip()
    raw_text = (
        (meta_description.get("content") if meta_description else None)
        or soup.get_text(" ", strip=True)
    ).strip()

    if not raw_title and not raw_text:
        raise EmptyExtractionError

    return {"raw_title": raw_title, "raw_text": raw_text}


def _fetch_general_web(url):
    # 예외는 잡지 않고 그대로 올려보낸다 — 안전하지 않은 URL은 여기서 거부된다.
    validate_fetch_url(url, resolver=socket.getaddrinfo)

    response = httpx.get(
        url,
        timeout=_GENERAL_WEB_TIMEOUT_SECONDS,
        headers={"User-Agent": _GENERAL_WEB_USER_AGENT},
    )
    # httpx의 .text는 응답 인코딩(모르면 자체 추정, 그래도 없으면 UTF-8)으로
    # 이미 디코딩하고 깨진 바이트는 대체 문자로 넘긴다 — 별도 디코딩이 필요 없다.
    html = response.text
    if len(html.encode("utf-8", errors="replace")) > _GENERAL_WEB_MAX_RESPONSE_BYTES:
        raise ResponseTooLargeError

    return _parse_raw_fields(html)


def fetch_event_text(*, url):
    hostname = urlsplit(url).hostname
    if hostname in _CAPTION_HOSTNAMES:
        return _fetch_instagram_caption(url)
    return _fetch_general_web(url)
