"""이벤트 URL을 실제로 읽어오는 결정론적 읽기 단계다. 모델을 쓰지 않는다 —
호스트만 보고 인스타·X 캡션 경로와 일반 웹 경로 중 하나로 그대로 분기한다."""
import html
import re
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

# 인스타는 브라우저 UA를 쓰면 og:description 메타 태그 자체가 안 나온다(실측
# 2026-09-11). 러너 자체 식별 UA를 쓴다 — 서버의 자기 식별 관례
# (drafts/fetching.py의 USER_AGENT = "TakuLifeBot/1.0")와 같은 결로 맞춘다.
_CAPTION_USER_AGENT = "TakuLifeRunner/1.0"

# 좋아요·댓글 수(천 단위 쉼표 허용)·계정명·영문 월 날짜 접두. 계정명에는
# 공백이 있을 수 있어 비탐욕 매치로 " on "까지만 잡는다. 본문에 개행이 있어도
# 접두 자체(줄바꿈 없는 한 줄)만 매치하면 되므로 DOTALL은 필요 없다.
_CAPTION_PREFIX_RE = re.compile(
    r'^[\d,]+\s+likes,\s+[\d,]+\s+comments\s+-\s+.+?\s+on\s+'
    r'[A-Za-z]+\s+\d{1,2},\s+\d{4}:\s+"'
)
# 접미: 닫는 인용부호 + 마침표 + 문자열 끝까지의 공백(있으면).
_CAPTION_SUFFIX_RE = re.compile(r'"\.\s*$')

# 계획서가 정한 원문 저장 상한(raw_text≤5,000자)과 같은 값이다.
CAPTION_MAX_LENGTH = 5000
_CAPTION_TRUNCATION_MARKER = "…(절단됨)"


class ResponseTooLargeError(Exception):
    pass


class EmptyExtractionError(Exception):
    pass


def _fetch_instagram_caption(url):
    response = httpx.get(
        url,
        timeout=_GENERAL_WEB_TIMEOUT_SECONDS,
        headers={"User-Agent": _CAPTION_USER_AGENT},
    )
    soup = BeautifulSoup(response.text, "html.parser")
    tag = soup.find("meta", attrs={"property": "og:description"})
    if tag is None:
        return None

    content = html.unescape(tag.get("content") or "")

    prefix_match = _CAPTION_PREFIX_RE.match(content)
    if prefix_match is None:
        # 접두 형태가 안 맞으면 원문을 그대로 넘기지 않는다 — 좋아요 수·게시일이
        # 캡션 본문과 섞여 해석 단계가 게시일을 행사 시작일로 오인할 수 있다.
        # 이 게시물만 건너뛰고 다음 실행에서 재시도한다.
        return None

    body = content[prefix_match.end() :]
    suffix_match = _CAPTION_SUFFIX_RE.search(body)
    if suffix_match is not None:
        body = body[: suffix_match.start()]

    if len(body) > CAPTION_MAX_LENGTH:
        # 표시 문구 길이까지 포함해 최종 길이가 상한을 넘지 않게 자른다.
        cutoff = CAPTION_MAX_LENGTH - len(_CAPTION_TRUNCATION_MARKER)
        body = body[:cutoff] + _CAPTION_TRUNCATION_MARKER

    # 개행·공백은 건드리지 않는다 — 해석 단계가 줄 구조를 단서로 쓴다.
    return body


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
