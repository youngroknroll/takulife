"""local_runner.page_fetch — 이벤트 URL 호스트별 읽기 경로 분기.
인스타·X는 캡션 경로로, 그 외(알 수 없는 호스트 포함)는 일반 웹 경로로 간다."""
import socket

import pytest

from local_runner.page_fetch import fetch_event_text
from local_runner.url_safety import UnsafeFetchUrlError


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "url, expected_path",
    [
        ("https://www.instagram.com/p/Dck7ZVUoG4i/", "caption"),
        ("https://x.com/example/status/1234567890", "caption"),
        ("https://official-site.example.com/event", "web"),
    ],
    ids=["인스타", "X", "알_수_없는_호스트"],
)
def test_이벤트_URL은_호스트별로_읽기_경로가_정해지고_알_수_없는_호스트는_일반_웹으로_간다(
    url, expected_path, monkeypatch
):
    caption_calls = []
    web_calls = []

    monkeypatch.setattr(
        "local_runner.page_fetch._fetch_instagram_caption",
        lambda url: caption_calls.append(url),
    )
    monkeypatch.setattr(
        "local_runner.page_fetch._fetch_general_web",
        lambda url: web_calls.append(url),
    )

    fetch_event_text(url=url)

    if expected_path == "caption":
        assert caption_calls == [url]
        assert web_calls == []
    else:
        assert web_calls == [url]
        assert caption_calls == []


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
