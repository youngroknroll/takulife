"""drafts.fetching.fetch_html이 DNS로 검증한 IP에 실제로 연결하는지 검증한다.
validate_fetch_url은 스텁하지 않고 fake_resolver로 실제 DNS 조회만 대체해, 검증에
쓰인 IP와 연결에 쓰이는 IP가 같은지(TOCTOU 방지)를 확인한다."""
import httpx
import pytest

import drafts.fetching as fetching
from drafts.fetching import fetch_html


pytestmark = pytest.mark.unit


def test_도메인_호스트를_가져오면_검증된_IP로_연결하고_Host_헤더는_원래_호스트를_유지한다(
    monkeypatch, install_mock_transport, fake_resolver
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    install_mock_transport(monkeypatch, handler)
    monkeypatch.setattr(fetching.socket, "getaddrinfo", fake_resolver("93.184.216.34"))

    fetch_html("http://example.com/")

    request = calls[0]
    assert request.url.host == "93.184.216.34"
    assert request.headers["host"] == "example.com"
    assert len(request.headers.get_list("host")) == 1


def test_https_요청은_sni_hostname_확장에_원래_호스트를_실어_TLS_검증을_유지한다(
    monkeypatch, install_mock_transport, fake_resolver
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    install_mock_transport(monkeypatch, handler)
    monkeypatch.setattr(fetching.socket, "getaddrinfo", fake_resolver("93.184.216.34"))

    fetch_html("https://example.com/")

    request = calls[0]
    assert request.extensions.get("sni_hostname") == "example.com"


def test_검증_이후_리졸버_응답이_바뀌어도_연결은_검증_시점_IP로_간다(
    monkeypatch, install_mock_transport
):
    calls = []
    resolve_count = 0

    def handler(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    def resolve_then_flip(_hostname, _port, *, type=None):
        # fetch_html은 사전 검증(1회)과 홉 내 검증(1회)에서 각각 리졸버를 부른다.
        # 둘 다 공인 IP를 받게 해 검증을 통과시키고, 그 이후(httpx가 재조회한다면)만
        # 사설 IP로 바꿔 "연결이 검증 시점 IP를 그대로 쓰는지"만 관찰한다.
        nonlocal resolve_count
        resolve_count += 1
        ip = "93.184.216.34" if resolve_count <= 2 else "10.1.2.3"
        return [(2, type, 6, "", (ip, 0))]

    install_mock_transport(monkeypatch, handler)
    monkeypatch.setattr(fetching.socket, "getaddrinfo", resolve_then_flip)

    fetch_html("https://example.com/")

    assert calls[0].url.host == "93.184.216.34"


def test_리다이렉트_각_홉도_그_홉에서_검증된_IP로_연결한다(
    monkeypatch, install_mock_transport, fake_resolver
):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "93.184.216.34":
            return httpx.Response(302, headers={"location": "https://cdn.example.net/asset"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    install_mock_transport(monkeypatch, handler)
    resolver = fake_resolver({"example.com": "93.184.216.34", "cdn.example.net": "9.9.9.9"})
    monkeypatch.setattr(fetching.socket, "getaddrinfo", resolver)

    fetch_html("https://example.com/")

    assert calls[0].url.host == "93.184.216.34"
    assert calls[0].headers["host"] == "example.com"
    assert calls[1].url.host == "9.9.9.9"
    assert calls[1].headers["host"] == "cdn.example.net"


def test_상대경로_리다이렉트는_원래_URL을_기준으로_다음_홉을_계산한다(
    monkeypatch, install_mock_transport, fake_resolver
):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(302, headers={"location": "/next"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    install_mock_transport(monkeypatch, handler)
    monkeypatch.setattr(fetching.socket, "getaddrinfo", fake_resolver("93.184.216.34"))

    fetch_html("https://example.com/")

    # urljoin이 IP 치환 URL이 아니라 논리(호스트명) URL을 기준으로 계산됨을 고정한다.
    assert calls[1].headers["host"] == "example.com"
    assert calls[1].url.path == "/next"
