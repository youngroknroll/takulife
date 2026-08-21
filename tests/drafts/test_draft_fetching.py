"""drafts.fetching.fetch_html을 httpx MockTransport로 검증한다. 리다이렉트 상한,
content-type 거부, 응답 크기 상한, 정상 디코딩을 다루며, validate_fetch_url은
전용 테스트가 따로 있어 여기서는 스텁 처리한다."""
import httpx
import pytest
from django.test import override_settings

from drafts.fetching import (
    MAX_RESPONSE_BYTES,
    USER_AGENT,
    FetchError,
    FetchHttpStatusError,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
    fetch_html,
)


pytestmark = pytest.mark.unit


def _install(monkeypatch, install_mock_transport, handler):
    install_mock_transport(monkeypatch, handler, stub_validate_fetch_url=True)


def test_정상_응답은_디코딩된_HTML을_반환한다(monkeypatch, install_mock_transport):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/html; charset=utf-8"},
            content="<html>본문</html>".encode("utf-8"),
        )

    _install(monkeypatch, install_mock_transport, handler)
    assert "본문" in fetch_html("https://example.com/")
    # 검증이 스텁돼 IP가 없으면(None) 치환 없이 원래 호스트로 연결해야 한다.
    assert calls[0].url.host == "example.com"


def test_HTML이_아닌_content_type은_거부된다(monkeypatch, install_mock_transport):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/json"}, content=b"{}")

    _install(monkeypatch, install_mock_transport, handler)
    with pytest.raises(UnsupportedContentTypeError):
        fetch_html("https://example.com/data")


def test_응답_크기가_상한을_넘으면_거부된다(monkeypatch, install_mock_transport):
    def handler(request):
        body = b"x" * (MAX_RESPONSE_BYTES + 1)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=body)

    _install(monkeypatch, install_mock_transport, handler)
    with pytest.raises(ResponseTooLargeError):
        fetch_html("https://example.com/big")


def test_리다이렉트가_상한을_넘으면_FetchError를_발생시킨다(monkeypatch, install_mock_transport):
    def handler(request):
        return httpx.Response(302, headers={"location": "https://example.com/next"})

    _install(monkeypatch, install_mock_transport, handler)
    with pytest.raises(FetchError):
        fetch_html("https://example.com/loop")


def test_전송_계층_오류는_FetchError로_매핑된다(monkeypatch, install_mock_transport):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    _install(monkeypatch, install_mock_transport, handler)
    with pytest.raises(FetchError):
        fetch_html("https://example.com/down")


def test_명시적으로_허용한_xml_content_type은_수용된다(monkeypatch, install_mock_transport):
    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "application/rss+xml"}, content=b"<rss></rss>"
        )

    _install(monkeypatch, install_mock_transport, handler)
    result = fetch_html(
        "https://example.com/feed.xml", allowed_content_types=("application/rss+xml",)
    )
    assert result == "<rss></rss>"


def test_명시적_허용_content_type_목록은_기본값을_대체하고_병합하지_않는다(monkeypatch, install_mock_transport):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    _install(monkeypatch, install_mock_transport, handler)
    with pytest.raises(UnsupportedContentTypeError):
        fetch_html("https://example.com/feed.xml", allowed_content_types=("application/rss+xml",))


@pytest.mark.parametrize("status", [404, 500], ids=["404_응답", "500_응답"])
def test_HTTP_오류_응답은_상태코드를_포함한_FetchHttpStatusError를_발생시킨다(monkeypatch, status, install_mock_transport):
    def handler(request):
        return httpx.Response(status, headers={"content-type": "text/html"}, content=b"")

    _install(monkeypatch, install_mock_transport, handler)
    with pytest.raises(FetchHttpStatusError) as exc_info:
        fetch_html("https://example.com/missing")

    assert exc_info.value.status_code == status


def test_xml_content_type_응답에도_크기_상한이_적용된다(monkeypatch, install_mock_transport):
    def handler(request):
        body = b"x" * (MAX_RESPONSE_BYTES + 1)
        return httpx.Response(200, headers={"content-type": "application/rss+xml"}, content=body)

    _install(monkeypatch, install_mock_transport, handler)
    with pytest.raises(ResponseTooLargeError):
        fetch_html("https://example.com/feed.xml", allowed_content_types=("application/rss+xml",))


def test_연락처_설정이_없으면_기본_User_Agent_값을_사용한다(monkeypatch, install_mock_transport):
    captured = {}

    def handler(request):
        captured["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    _install(monkeypatch, install_mock_transport, handler)
    fetch_html("https://example.com/")
    assert captured["user_agent"] == USER_AGENT


@override_settings(DRAFT_FETCH_CONTACT="https://example.com/about")
def test_연락처_설정이_있으면_User_Agent에_연락처를_덧붙인다(monkeypatch, install_mock_transport):
    captured = {}

    def handler(request):
        captured["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    _install(monkeypatch, install_mock_transport, handler)
    fetch_html("https://example.com/")
    assert captured["user_agent"] == "TakuLifeBot/1.0 (+https://example.com/about)"


@override_settings(DRAFT_FETCH_CONTACT="https://example.com/about\n")
def test_연락처_설정_끝의_공백은_User_Agent에서_제거된다(monkeypatch, install_mock_transport):
    # .env 값 끝에 실수로 남은 개행이 User-Agent 헤더로 새어 나가는 것을 막는다.
    captured = {}

    def handler(request):
        captured["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    _install(monkeypatch, install_mock_transport, handler)
    fetch_html("https://example.com/")
    assert captured["user_agent"] == "TakuLifeBot/1.0 (+https://example.com/about)"
