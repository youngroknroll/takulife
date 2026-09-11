"""local_runner.exploration_flow — 탐색 출력의 events·sources 분리 파싱과
상한 절단을 검증한다."""
import pytest

from local_runner.exploration_flow import (
    EXPLORATION_MAX_EVENTS,
    EXPLORATION_MAX_SOURCES,
    parse_exploration_output,
    run_exploration_flow,
)
from local_runner.page_fetch import BlockedResponseError


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


class _FakeClient:
    """실제 네트워크 없이 러너→서버 호출을 기록만 하는 가짜 클라이언트.
    known_urls는 넘겨받은 URL을 전부 모르는 것으로 답한다(둘 다 모른다)."""

    def __init__(self):
        self.known_urls_calls = []
        self.submit_event_calls = []
        self.submit_candidate_calls = []

    def known_urls(self, *, urls):
        self.known_urls_calls.append(list(urls))
        return list(urls)

    def submit_event(self, *, run_id, lease_token, event):
        self.submit_event_calls.append(event)
        return {"status": "created", "draft_id": 1}

    def submit_candidate(self, *, run_id, lease_token, candidate):
        self.submit_candidate_calls.append(candidate)
        return {"status": "created"}


def test_탐색_흐름은_known_필터_후_읽기_해석_제출을_순서대로_수행하고_실패_항목을_건너뛴다():
    events = [
        {"url": "https://example.com/event-1", "platform": "web"},
        {"url": "https://example.com/event-2", "platform": "web"},
    ]
    sources = [
        {"name": "공식 홈페이지", "url": "https://example.com/feed", "source_type": "rss"}
    ]

    fetch_calls = []
    interpret_calls = []

    def fake_fetch_text(*, url):
        fetch_calls.append(url)
        if url == events[0]["url"]:
            return "원문 텍스트"
        return None  # 둘째 URL은 읽기 실패

    def fake_interpret(*, text, url, platform):
        interpret_calls.append((text, url, platform))
        return {
            "source_url": url,
            "platform": platform,
            "is_event": True,
            "fields": {"title": "제목"},
        }

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=sources,
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    # 알려진 URL 조회는 이벤트 2건으로 한 번만 호출된다.
    assert client.known_urls_calls == [[events[0]["url"], events[1]["url"]]]

    # 첫 URL은 읽기→해석→제출까지 이어진다.
    assert fetch_calls == [events[0]["url"], events[1]["url"]]
    assert interpret_calls == [("원문 텍스트", events[0]["url"], "web")]
    assert len(client.submit_event_calls) == 1
    assert client.submit_event_calls[0]["source_url"] == events[0]["url"]

    # 소스는 목록형·계정형 구분 없이 그대로 서버에 넘긴다.
    assert client.submit_candidate_calls == [sources[0]]

    # 반환 요약이 완료 보고에 그대로 실리는 시도·실패 수다.
    assert summary == {"events_attempted": 2, "events_failed": 1}


def test_일반_웹_응답이_403이나_429면_그_URL만_건너뛰고_같은_호스트_두_번째부터는_호스트를_건너뛴다():
    events = [
        {"url": "https://blocked.example.com/event-1", "platform": "web"},
        {"url": "https://blocked.example.com/event-2", "platform": "web"},
        {"url": "https://ok.example.com/event-3", "platform": "web"},
    ]

    fetch_calls = []
    interpret_calls = []

    def fake_fetch_text(*, url):
        fetch_calls.append(url)
        if url == events[0]["url"]:
            raise BlockedResponseError(403)
        if url == events[1]["url"]:
            # 같은 호스트가 이미 차단됐어야 하므로 이 분기는 절대 타면 안 된다.
            raise BlockedResponseError(429)
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        interpret_calls.append((text, url, platform))
        return {
            "source_url": url,
            "platform": platform,
            "is_event": True,
            "fields": {"title": "제목"},
        }

    client = _FakeClient()

    run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    # 첫째 URL만 실제로 읽기가 호출된다 — 같은 호스트의 둘째는 실행 내내
    # 건너뛰어야 하므로 아예 호출되지 않는다. 셋째는 다른 호스트라 영향이 없다.
    assert fetch_calls == [events[0]["url"], events[2]["url"]]
    assert interpret_calls == [("원문 텍스트", events[2]["url"], "web")]
    assert len(client.submit_event_calls) == 1
    assert client.submit_event_calls[0]["source_url"] == events[2]["url"]
