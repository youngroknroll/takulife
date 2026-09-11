"""local_runner.exploration_flow — 탐색 출력의 events·sources 분리 파싱과
상한 절단을 검증한다."""
import pytest

from local_runner.exploration_flow import (
    EXPLORATION_MAX_EVENTS,
    EXPLORATION_MAX_SOURCES,
    parse_exploration_output,
)


pytestmark = pytest.mark.unit


def _make_event(i):
    return {
        "url": f"https://example.com/event-{i}",
        "platform": "web",
        "title_guess": f"이벤트 {i}",
        "is_event": True,
        "duplicate_urls": [],
    }


def _make_source(i):
    return {
        "name": f"소스 {i}",
        "url": f"https://example.com/source-{i}",
        "source_type": "html",
        "official_basis": "공식 도메인",
        "note": "",
    }


def test_탐색_출력의_events와_sources를_분리_파싱하고_상한을_넘는_항목은_잘라낸다():
    data = {
        "events": [_make_event(i) for i in range(EXPLORATION_MAX_EVENTS + 1)],
        "sources": [_make_source(i) for i in range(EXPLORATION_MAX_SOURCES + 1)],
    }

    result = parse_exploration_output(data=data)

    assert len(result["events"]) == EXPLORATION_MAX_EVENTS
    assert [event["url"] for event in result["events"]] == [
        f"https://example.com/event-{i}" for i in range(EXPLORATION_MAX_EVENTS)
    ]

    assert len(result["sources"]) == EXPLORATION_MAX_SOURCES
    assert [source["url"] for source in result["sources"]] == [
        f"https://example.com/source-{i}" for i in range(EXPLORATION_MAX_SOURCES)
    ]

    # 탐색은 공식 여부를 판단하지 않는다 — 그 필드는 해석 단계로 이관됐다.
    for event in result["events"]:
        assert "judgment" not in event
        assert "official_basis" not in event
