"""local_runner.page_fetch — 이벤트 URL 호스트별 읽기 경로 분기.
인스타는 캡션 경로, X는 게시물(syndication) 경로, 그 외(알 수 없는 호스트
포함)는 일반 웹 경로로 간다."""
import re
import socket
from urllib.parse import parse_qs, urlsplit

import pytest

import local_runner.page_fetch as page_fetch
from local_runner.page_fetch import CAPTION_MAX_LENGTH, fetch_event_text
from local_runner.url_safety import UnsafeFetchUrlError


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "url, expected_path",
    [
        ("https://www.instagram.com/p/Dck7ZVUoG4i/", "caption"),
        ("https://x.com/example/status/1234567890", "x"),
        ("https://official-site.example.com/event", "web"),
    ],
    ids=["인스타", "X", "알_수_없는_호스트"],
)
def test_이벤트_URL은_호스트별로_읽기_경로가_정해지고_알_수_없는_호스트는_일반_웹으로_간다(
    url, expected_path, monkeypatch
):
    caption_calls = []
    x_calls = []
    web_calls = []

    monkeypatch.setattr(
        "local_runner.page_fetch._fetch_instagram_caption",
        lambda url: caption_calls.append(url),
    )
    monkeypatch.setattr(
        "local_runner.page_fetch._fetch_x_post",
        lambda url: x_calls.append(url),
    )
    monkeypatch.setattr(
        "local_runner.page_fetch._fetch_general_web",
        lambda url: web_calls.append(url),
    )

    fetch_event_text(url=url)

    if expected_path == "caption":
        assert caption_calls == [url]
        assert x_calls == []
        assert web_calls == []
    elif expected_path == "x":
        assert x_calls == [url]
        assert caption_calls == []
        assert web_calls == []
    else:
        assert web_calls == [url]
        assert caption_calls == []
        assert x_calls == []


@pytest.mark.contract
def test_사설_루프백_링크로컬_IP로_해석되는_이벤트_URL은_러너가_GET하지_않는다(monkeypatch):
    # 실제 socket.getaddrinfo·httpx.get을 직접 패치한다 — 안전 검사가 서버
    # 판정을 복제한 어느 내부 모듈에서 이 둘을 어떤 이름으로 다시 임포트하든
    # 관계없이, 실제로 호출되는 지점은 이 두 전역 심볼뿐이기 때문이다.
    def fake_getaddrinfo(host, port, type=None):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))]

    get_calls = []

    monkeypatch.setattr("socket.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(
        "httpx.get", lambda *args, **kwargs: get_calls.append((args, kwargs))
    )

    with pytest.raises(UnsafeFetchUrlError):
        fetch_event_text(url="https://official-site.example.com/event")

    assert get_calls == []


class _FakeResponse:
    def __init__(self, html, status_code=200):
        self.text = html
        self.status_code = status_code

    def raise_for_status(self):
        pass


def _safe_getaddrinfo(host, port, type=None):
    # example.com의 실제 공인 IP — 안전 검사를 통과시키는 용도일 뿐 실제
    # 네트워크를 타지 않는다(httpx.get 자체를 스텁으로 갈아끼운다).
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def _og_title_우선():
    html = (
        '<html><head><meta property="og:title" content="OG 제목">'
        "<title>일반 제목</title></head><body>본문</body></html>"
    )
    return html, "OG 제목", None


def _title_대체():
    html = "<html><head><title>일반 제목</title></head><body>본문</body></html>"
    return html, "일반 제목", None


def _description_우선():
    html = (
        '<html><head><meta name="description" content="설명 요약"></head>'
        "<body>본문 내용입니다</body></html>"
    )
    return html, None, "설명 요약"


def _본문_대체():
    html = "<html><head></head><body>본문 내용입니다</body></html>"
    return html, None, "본문 내용입니다"


@pytest.mark.parametrize(
    "make_case",
    [_og_title_우선, _title_대체, _description_우선, _본문_대체],
    ids=["og_title_우선", "title_대체", "description_우선", "본문_대체"],
)
def test_일반_웹_페이지_텍스트는_og_title_title_description_본문_순으로_추출된다(
    make_case, monkeypatch
):
    html, expected_title, expected_text = make_case()
    captured = {}

    def fake_get(url, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return _FakeResponse(html)

    monkeypatch.setattr("local_runner.page_fetch.socket.getaddrinfo", _safe_getaddrinfo)
    monkeypatch.setattr("local_runner.page_fetch.httpx.get", fake_get)

    result = fetch_event_text(url="https://official-site.example.com/event")

    if expected_title is not None:
        assert result["raw_title"] == expected_title
    if expected_text is not None:
        assert result["raw_text"] == expected_text

    # 일반 웹은 브라우저 UA를 쓴다 — 인스타 경로만 예외다.
    headers = captured["headers"]
    assert headers is not None
    assert "Mozilla" in headers.get("User-Agent", "")


def _정상_추출():
    # 실측 표본(Dck7ZVUoG4i, 2026-09-11)의 형태를 그대로 쓴다. &amp;amp;는
    # 실제 관측되는 이중 이스케이프를 흉내낸다 — bs4가 속성값을 한 번 풀면
    # "&amp;"(글자 그대로)가 남고, 캡션 분리 함수가 한 번 더 풀어야 "&"가 된다.
    og_description_html_source = (
        '<html><head><meta property="og:description" '
        'content="1,768 likes, 9 comments - webtoonfriends on August 28, 2026: '
        "&quot;🥀 〈시든 꽃에 눈물을〉 팝업스토어 &amp;amp; 〈태하의 방〉 D-1\n\n"
        "드디어 내일, 〈태하의 방〉 팝업스토어 OPEN.\n신상품 MD부터 ... "
        '#웹툰프렌즈 #시든꽃에눈물을 #태하의방 #네이버웹툰 #팝업스토어&quot;. "></head>'
        "<body></body></html>"
    )
    expected = (
        "🥀 〈시든 꽃에 눈물을〉 팝업스토어 & 〈태하의 방〉 D-1\n\n"
        "드디어 내일, 〈태하의 방〉 팝업스토어 OPEN.\n신상품 MD부터 ... "
        "#웹툰프렌즈 #시든꽃에눈물을 #태하의방 #네이버웹툰 #팝업스토어"
    )
    return og_description_html_source, expected


def _접두_형태_불일치():
    html = (
        '<html><head><meta property="og:description" '
        'content="이 페이지를 사용할 수 없습니다."></head><body></body></html>'
    )
    return html, None


@pytest.mark.parametrize(
    "make_case",
    [_정상_추출, _접두_형태_불일치],
    ids=["정상_추출", "접두_형태_불일치"],
)
def test_og_description에서_좋아요_댓글_계정_날짜_접두와_닫는_인용부호_접미를_떼고_개행은_보존하며_접두가_안_맞으면_건너뛴다(
    make_case, monkeypatch
):
    html, expected = make_case()
    captured = {}

    def fake_get(url, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return _FakeResponse(html)

    monkeypatch.setattr("local_runner.page_fetch.httpx.get", fake_get)

    result = page_fetch._fetch_instagram_caption(
        "https://www.instagram.com/p/Dck7ZVUoG4i/"
    )

    assert result == expected

    headers = captured["headers"]
    assert headers is not None
    user_agent = headers.get("User-Agent", "")
    # 러너 자체 식별 UA를 쓴다 — 데스크톱 브라우저 UA는 이 메타 태그 자체가
    # 안 나온다(실측). 서버의 자기 식별 관례(drafts/fetching.py의
    # USER_AGENT = "TakuLifeBot/1.0")와 같은 결로 맞춘다.
    assert "Mozilla" not in user_agent
    assert "TakuLife" in user_agent


def test_상한을_넘는_캡션은_절단되고_절단_표시가_남는다(monkeypatch):
    long_body = "가" * 6000
    html_source = (
        '<html><head><meta property="og:description" '
        'content="1,000 likes, 2 comments - testaccount on January 1, 2026: &quot;'
        + long_body
        + '&quot;. "></head><body></body></html>'
    )

    def fake_get(url, **kwargs):
        return _FakeResponse(html_source)

    monkeypatch.setattr("local_runner.page_fetch.httpx.get", fake_get)

    result = page_fetch._fetch_instagram_caption(
        "https://www.instagram.com/p/Dck7ZVUoG4i/"
    )

    assert len(result) <= CAPTION_MAX_LENGTH
    assert result.endswith("…(절단됨)")


# ---------------------------------------------------------------------------
# TR-29 — S5: x.com·twitter.com의 /<handle>/status/<숫자 id> URL은
# cdn.syndication.twimg.com/tweet-result?id=<id>&token=... 로 읽어 JSON의
# text를 그대로 본문으로 반환한다.
# ---------------------------------------------------------------------------


class _FakeSyndicationResponse:
    def __init__(self, payload=None, status_code=200, content=b"", json_error=False):
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self.text = ""
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("잘못된 JSON")
        return self._payload


def test_X_상태_URL은_고정_syndication_호스트에서_트윗_본문을_그대로_반환한다(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return _FakeSyndicationResponse({"text": "치이카와 팝업스토어 서울 10월 1일~10월 14일"})

    monkeypatch.setattr(
        "local_runner.page_fetch.socket.getaddrinfo", _safe_getaddrinfo
    )
    monkeypatch.setattr("local_runner.page_fetch.httpx.get", fake_get)

    result = fetch_event_text(
        url="https://x.com/somehandle/status/1234567890123456789"
    )

    assert result == "치이카와 팝업스토어 서울 10월 1일~10월 14일"

    requested = urlsplit(captured["url"])
    assert requested.hostname == "cdn.syndication.twimg.com"
    assert requested.path == "/tweet-result"
    query = parse_qs(requested.query)
    assert query["id"] == ["1234567890123456789"]
    # token 값 자체는 계산식(구현 단계)의 몫이다 — 여기서는 파라미터 존재만 본다.
    assert "token" in query


# ---------------------------------------------------------------------------
# TR-30 — S5: syndication 응답이 실패 형태(상태코드·빈 JSON·JSON 파싱 오류·
# 빈 text)면 예외 없이 None을 반환한다.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_response",
    [
        lambda: _FakeSyndicationResponse(
            status_code=404, payload={"text": "정상처럼 보이는 본문"}
        ),
        lambda: _FakeSyndicationResponse(payload={}),
        lambda: _FakeSyndicationResponse(json_error=True),
        lambda: _FakeSyndicationResponse(payload={"text": ""}),
    ],
    ids=["상태코드_404", "본문_text_없음", "JSON_파싱_오류", "text_빈_문자열"],
)
def test_X_syndication_응답이_실패_형태면_None을_반환한다(make_response, monkeypatch):
    monkeypatch.setattr(
        "local_runner.page_fetch.socket.getaddrinfo", _safe_getaddrinfo
    )
    monkeypatch.setattr(
        "local_runner.page_fetch.httpx.get", lambda url, **kwargs: make_response()
    )

    result = fetch_event_text(
        url="https://x.com/somehandle/status/1234567890123456789"
    )

    assert result is None


# ---------------------------------------------------------------------------
# TR-31 — S5: 게시물(status) 형태가 아닌 X URL은 네트워크 요청 없이 None이다.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/somehandle",
        "https://x.com/i/status/abc",
        "https://twitter.com/somehandle/status/123/photo/1",
    ],
    ids=["프로필_URL", "id가_숫자가_아님", "사진_하위_경로"],
)
def test_게시물_형태가_아닌_X_URL은_요청_없이_None이다(url, monkeypatch):
    get_calls = []

    monkeypatch.setattr(
        "local_runner.page_fetch.httpx.get",
        lambda *args, **kwargs: get_calls.append((args, kwargs)),
    )

    result = fetch_event_text(url=url)

    assert result is None
    assert get_calls == []


# ---------------------------------------------------------------------------
# TR-32 — S5: syndication 응답 본문이 상한(1,000,000바이트)을 넘으면 None이다.
# ---------------------------------------------------------------------------


def test_X_syndication_응답이_상한을_넘으면_None이다(monkeypatch):
    oversized_content = b"x" * 1_000_001

    monkeypatch.setattr(
        "local_runner.page_fetch.socket.getaddrinfo", _safe_getaddrinfo
    )
    monkeypatch.setattr(
        "local_runner.page_fetch.httpx.get",
        lambda url, **kwargs: _FakeSyndicationResponse(
            payload={"text": "본문"}, content=oversized_content
        ),
    )

    result = fetch_event_text(
        url="https://x.com/somehandle/status/1234567890123456789"
    )

    assert result is None


def test_X_토큰은_숫자와_소문자로만_구성되고_0과_점을_포함하지_않는다():
    token = page_fetch._x_syndication_token("1234567890123456789")

    assert token != ""
    assert re.fullmatch(r"[1-9a-z]+", token)
