"""local_runner.exploration_flow — 탐색 출력의 events·sources 분리 파싱과
상한 절단을 검증한다."""
import httpx
import pytest

from local_runner.exploration_flow import (
    EXPLORATION_MAX_EVENTS,
    EXPLORATION_MAX_SOURCES,
    LeaseLostError,
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


def test_탐색_출력의_events와_sources는_dict가_아닌_항목이_제거된_뒤_상한이_적용된다():
    events = ["문자열", None, 42, *[_make_event(i) for i in range(EXPLORATION_MAX_EVENTS)]]
    sources = ["문자열", None, 3.14, *[_make_source(i) for i in range(EXPLORATION_MAX_SOURCES)]]

    result = parse_exploration_output(data={"events": events, "sources": sources})

    assert len(result["events"]) == EXPLORATION_MAX_EVENTS
    assert all(isinstance(event, dict) for event in result["events"])
    assert [event["url"] for event in result["events"]] == [
        f"https://example.com/event-{i}" for i in range(EXPLORATION_MAX_EVENTS)
    ]

    assert len(result["sources"]) == EXPLORATION_MAX_SOURCES
    assert all(isinstance(source, dict) for source in result["sources"])
    assert [source["url"] for source in result["sources"]] == [
        f"https://example.com/source-{i}" for i in range(EXPLORATION_MAX_SOURCES)
    ]


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


def _make_http_status_error(status_code):
    request = httpx.Request("POST", "https://example.com/x")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"status {status_code}", request=request, response=response)


class _LeaseLostAtSubmitClient(_FakeClient):
    """제출 중 지정한 항목(첫 이벤트 또는 첫 소스)에서만 409를 내는 가짜 클라이언트."""

    def __init__(self, *, fail_at):
        super().__init__()
        self._fail_at = fail_at

    def submit_event(self, *, run_id, lease_token, event):
        self.submit_event_calls.append(event)
        if self._fail_at == "event" and len(self.submit_event_calls) == 1:
            raise _make_http_status_error(409)
        return {"status": "created", "draft_id": 1}

    def submit_candidate(self, *, run_id, lease_token, candidate):
        self.submit_candidate_calls.append(candidate)
        if self._fail_at == "source" and len(self.submit_candidate_calls) == 1:
            raise _make_http_status_error(409)
        return {"status": "created"}


@pytest.mark.parametrize(
    "fail_at",
    ["event", "source"],
    ids=["이벤트_제출_중_409", "소스_제출_중_409"],
)
def test_임대_상실_409는_남은_항목_처리를_즉시_멈추고_LeaseLostError를_낸다(fail_at):
    events = [
        {"url": "https://example.com/event-1", "platform": "web"},
        {"url": "https://example.com/event-2", "platform": "web"},
    ]
    sources = [
        {"name": "소스1", "url": "https://example.com/source-1", "source_type": "rss"},
        {"name": "소스2", "url": "https://example.com/source-2", "source_type": "rss"},
    ]

    fetch_calls = []

    def fake_fetch_text(*, url):
        fetch_calls.append(url)
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        return {
            "source_url": url,
            "platform": platform,
            "is_event": True,
            "fields": {"title": "제목"},
        }

    client = _LeaseLostAtSubmitClient(fail_at=fail_at)

    with pytest.raises(LeaseLostError):
        run_exploration_flow(
            client=client,
            run_id=1,
            lease_token="tok",
            events=events,
            sources=sources,
            fetch_text=fake_fetch_text,
            interpret=fake_interpret,
        )

    if fail_at == "event":
        # 첫 이벤트 제출에서 409가 났으므로 둘째 이벤트는 읽기조차 시도되지
        # 않고, 소스 처리는 아예 시작되지 않는다.
        assert fetch_calls == [events[0]["url"]]
        assert client.submit_event_calls == [
            {"source_url": events[0]["url"], "platform": "web", "is_event": True, "fields": {"title": "제목"}}
        ]
        assert client.submit_candidate_calls == []
    else:
        # 이벤트 둘은 정상 처리되고, 첫 소스 제출에서 409가 나므로 둘째
        # 소스는 제출 시도조차 되지 않는다.
        assert fetch_calls == [events[0]["url"], events[1]["url"]]
        assert len(client.submit_event_calls) == 2
        assert client.submit_candidate_calls == [sources[0]]


class _SkipNonLeaseErrorClient(_FakeClient):
    """지정한 항목의 첫 제출에서 409가 아닌 HTTP 오류를 내고 이후는 정상
    처리하는 가짜 클라이언트. 성공한 제출만 submit_*_calls에 남긴다."""

    def __init__(self, *, fail_at):
        super().__init__()
        self._fail_at = fail_at
        self.submit_event_attempts = []
        self.submit_candidate_attempts = []

    def submit_event(self, *, run_id, lease_token, event):
        self.submit_event_attempts.append(event)
        if self._fail_at == "event" and len(self.submit_event_attempts) == 1:
            raise _make_http_status_error(400)
        self.submit_event_calls.append(event)
        return {"status": "created", "draft_id": 1}

    def submit_candidate(self, *, run_id, lease_token, candidate):
        self.submit_candidate_attempts.append(candidate)
        if self._fail_at == "source" and len(self.submit_candidate_attempts) == 1:
            raise _make_http_status_error(400)
        self.submit_candidate_calls.append(candidate)
        return {"status": "created"}


@pytest.mark.parametrize(
    "fail_at",
    ["event", "source"],
    ids=["이벤트_400", "소스_400"],
)
def test_제출_중_409가_아닌_HTTP_오류는_그_항목만_건너뛰고_나머지를_계속_처리한다(fail_at):
    events = [
        {"url": "https://example.com/event-1", "platform": "web"},
        {"url": "https://example.com/event-2", "platform": "web"},
    ]
    sources = [
        {"name": "소스1", "url": "https://example.com/source-1", "source_type": "rss"},
        {"name": "소스2", "url": "https://example.com/source-2", "source_type": "rss"},
    ]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        return {
            "source_url": url,
            "platform": platform,
            "is_event": True,
            "fields": {"title": "제목"},
        }

    client = _SkipNonLeaseErrorClient(fail_at=fail_at)

    run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=sources,
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    if fail_at == "event":
        assert len(client.submit_event_attempts) == 2
        # 첫 이벤트는 400으로 건너뛰고 둘째만 실제로 제출된다.
        assert len(client.submit_event_calls) == 1
        assert client.submit_event_calls[0]["source_url"] == events[1]["url"]
    else:
        assert len(client.submit_candidate_attempts) == 2
        assert client.submit_candidate_calls == [sources[1]]
