"""local_runner.page_fetch — 이벤트 URL 호스트별 읽기 경로 분기.
인스타·X는 캡션 경로로, 그 외(알 수 없는 호스트 포함)는 일반 웹 경로로 간다."""
import pytest

from local_runner.page_fetch import fetch_event_text


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
