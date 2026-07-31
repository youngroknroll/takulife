"""회귀 방지: fetch_html은 최초 URL뿐 아니라 모든 리다이렉트 홉마다 SSRF 검사를
다시 수행해야 한다. httpx는 DNS를 직접 고정할 훅이 없어 IP 고정 대신 매 홉마다
validate_fetch_url의 실제 로직을 태우는 것이 지금의 SSRF 방어선이다. 다른 fetching
테스트와 달리 여기서는 validate_fetch_url을 스텁하지 않는다."""
import httpx
import pytest

import drafts.fetching as fetching
from drafts.fetching import fetch_html
from drafts.url_safety import UnsafeFetchUrlError, validate_fetch_url


pytestmark = pytest.mark.contract


def test_리다이렉트_대상이_사설_IP_리터럴이면_거부된다(monkeypatch, install_mock_transport):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    install_mock_transport(monkeypatch, handler)
    # resolver 인자만 제거한다. 리터럴 IP 분기는 애초에 DNS 조회가 필요 없다.
    monkeypatch.setattr(
        fetching, "validate_fetch_url", lambda url, **kwargs: validate_fetch_url(url)
    )

    with pytest.raises(UnsafeFetchUrlError):
        fetch_html("https://example.com/")

    assert len(calls) == 1


def test_리다이렉트_대상_호스트명이_사설_IP로_해석되면_거부된다(
    monkeypatch, install_mock_transport, fake_resolver
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://evil.example.com/"})

    install_mock_transport(monkeypatch, handler)
    resolver = fake_resolver({"example.com": "93.184.216.34", "evil.example.com": "10.1.2.3"})
    monkeypatch.setattr(fetching.socket, "getaddrinfo", resolver)

    with pytest.raises(UnsafeFetchUrlError):
        fetch_html("https://example.com/")

    assert len(calls) == 1
