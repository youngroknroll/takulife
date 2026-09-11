"""이벤트 URL을 실제로 읽어오는 결정론적 읽기 단계다. 모델을 쓰지 않는다 —
호스트만 보고 인스타·X 캡션 경로와 일반 웹 경로 중 하나로 그대로 분기한다."""
from urllib.parse import urlsplit

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


def _fetch_instagram_caption(url):
    # 다음 사이클: 인스타/X 게시물 페이지를 httpx로 가져와 캡션만 분리한다.
    pass


def _fetch_general_web(url):
    # 다음 사이클: SSRF 안전 검사 후 일반 웹 페이지를 httpx로 가져와 본문을 추출한다.
    pass


def fetch_event_text(*, url):
    hostname = urlsplit(url).hostname
    if hostname in _CAPTION_HOSTNAMES:
        return _fetch_instagram_caption(url)
    return _fetch_general_web(url)
