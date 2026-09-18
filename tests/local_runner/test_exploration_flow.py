"""local_runner.exploration_flow — 탐색 출력의 events·sources 분리 파싱과
상한 절단을 검증한다."""
import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
import pytest

from local_runner.claude_code_adapter import AdapterOutputError
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
        {
            "name": "공식 홈페이지",
            "url": "https://example.com/feed",
            "source_type": "rss",
            "source_country": "kr",
        }
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

    # 반환 요약이 완료 보고에 그대로 실리는 시도·실패·제외 수다.
    assert summary == {
        "events_attempted": 2,
        "events_failed": 1,
        "events_excluded": 0,
        "event_outcomes": [
            {"url": events[0]["url"], "outcome": "created", "reason": ""},
            {"url": events[1]["url"], "outcome": "failed", "reason": "fetch_empty"},
        ],
    }


class _AllKnownClient(_FakeClient):
    """넘겨받은 URL을 전부 이미 아는 것으로 답하는 가짜 클라이언트."""

    def known_urls(self, *, urls):
        self.known_urls_calls.append(list(urls))
        return []


def test_이미_알려진_URL은_읽기를_시도하지_않고_결과_목록에_skipped_known_url로_기록된다():
    events = [_make_event(1)]

    def fake_fetch_text(*, url):
        raise AssertionError("이미 알려진 URL은 읽기를 시도하면 안 된다")

    client = _AllKnownClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=None,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "skipped", "reason": "known_url"}
    ]


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


def test_같은_호스트가_이미_차단됐으면_읽기_없이_failed_host_blocked로_기록된다():
    events = [
        {"url": "https://blocked.example.com/event-1", "platform": "web"},
        {"url": "https://blocked.example.com/event-2", "platform": "web"},
    ]

    fetch_calls = []

    def fake_fetch_text(*, url):
        fetch_calls.append(url)
        raise BlockedResponseError(403)

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=None,
    )

    assert fetch_calls == [events[0]["url"]]
    assert summary["event_outcomes"][1] == {
        "url": events[1]["url"],
        "outcome": "failed",
        "reason": "host_blocked",
    }


def test_첫_차단_응답을_받은_이벤트는_failed_blocked로_기록된다():
    events = [{"url": "https://blocked.example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        raise BlockedResponseError(403)

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=None,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "failed", "reason": "blocked"}
    ]


def test_읽기가_빈_값이면_failed_fetch_empty로_기록된다():
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return None

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=None,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "failed", "reason": "fetch_empty"}
    ]


def test_해석이_JSON을_못_내면_failed_interpret_error로_기록된다():
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return {"raw_title": "제목", "raw_text": "본문"}

    def fake_interpret(*, text, url, platform):
        raise AdapterOutputError("could not recover JSON from adapter output")

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "failed", "reason": "interpret_error"}
    ]


def test_제목_없는_해석_결과는_failed_no_title로_기록된다():
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return {"raw_title": "제목", "raw_text": "본문"}

    def fake_interpret(*, text, url, platform):
        result = _interpreted_result()
        result["fields"]["title"] = ""
        return result

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "failed", "reason": "no_title"}
    ]
    assert summary["events_failed"] == 1


def test_해석이_행사가_아니라고_판정하면_excluded_not_event로_기록되고_제외_건수에_더해진다():
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return {"raw_title": "제목", "raw_text": "본문"}

    def fake_interpret(*, text, url, platform):
        result = _interpreted_result()
        result["is_event"] = False
        return result

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "excluded", "reason": "not_event"}
    ]
    assert summary["events_excluded"] == 1
    assert summary["events_failed"] == 0


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
        {
            "name": "소스1",
            "url": "https://example.com/source-1",
            "source_type": "rss",
            "source_country": "kr",
        },
        {
            "name": "소스2",
            "url": "https://example.com/source-2",
            "source_type": "rss",
            "source_country": "kr",
        },
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
        # 않고, 소스 처리는 아예 시작되지 않는다. 페이로드 모양 자체는
        # 결함 1 전용 테스트가 보므로 여기서는 호출 횟수·주소만 본다.
        assert fetch_calls == [events[0]["url"]]
        assert len(client.submit_event_calls) == 1
        assert client.submit_event_calls[0]["source_url"] == events[0]["url"]
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
        {
            "name": "소스1",
            "url": "https://example.com/source-1",
            "source_type": "rss",
            "source_country": "kr",
        },
        {
            "name": "소스2",
            "url": "https://example.com/source-2",
            "source_type": "rss",
            "source_country": "kr",
        },
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


# ---------------------------------------------------------------------------
# 실기동 결함 1 — 제출 페이로드에 흐름이 아는 값(주소·원문·출처명)이
# 빠져 서버가 전부 400으로 거부했다. 해석 모델은 이 값을 모른다 — 흐름이
# 채워야 한다. page_fetch.fetch_event_text의 반환 모양은 호스트마다
# 다르다(일반 웹은 {"raw_title", "raw_text"} dict, 인스타 캡션은 문자열
# 하나) — 흐름이 그 차이를 흡수해 raw_title·raw_text로 분해한다.
# ---------------------------------------------------------------------------


def _interpreted_result():
    return {
        "is_event": True,
        "judgment": "official",
        "official_basis": "공식 홈페이지 명시",
        "fields": {
            "title": "하츠네 미쿠 팝업스토어",
            "work_title": "하츠네 미쿠",
            "category": "popup_store",
            "region": "seoul",
            "location_name": "",
            "start_date": None,
            "end_date": None,
            "summary": "",
        },
        "confidence": 0.9,
        "note": "",
    }


def _submit_payload_case_일반_웹():
    return {
        "platform": "web",
        "fetched": {"raw_title": "웹 제목", "raw_text": "웹 본문"},
        "expected_raw_title": "웹 제목",
        "expected_raw_text": "웹 본문",
    }


def _submit_payload_case_인스타():
    return {
        "platform": "instagram",
        "fetched": "인스타 캡션 원문",
        "expected_raw_title": "",
        "expected_raw_text": "인스타 캡션 원문",
    }


@pytest.mark.parametrize(
    "make_case",
    [_submit_payload_case_일반_웹, _submit_payload_case_인스타],
    ids=["일반_웹", "인스타"],
)
def test_제출_페이로드에_흐름이_아는_주소_원문_출처명이_채워지고_해석이_낸_값은_보존된다(make_case):
    case = make_case()
    event = {"url": "https://example.com/event-1", "platform": case["platform"]}
    interpreted_result = _interpreted_result()

    def fake_fetch_text(*, url):
        return case["fetched"]

    def fake_interpret(*, text, url, platform):
        return interpreted_result

    client = _FakeClient()

    run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=[event],
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert len(client.submit_event_calls) == 1
    payload = client.submit_event_calls[0]

    required_keys = (
        "source_url",
        "raw_title",
        "raw_text",
        "fields",
        "confidence",
        "note",
        "platform",
        "judgment",
        "official_basis",
        "source_name",
    )
    for key in required_keys:
        assert key in payload

    # 흐름이 아는 값 — 해석 모델은 낼 수 없다.
    assert payload["source_url"] == event["url"]
    assert payload["raw_title"] == case["expected_raw_title"]
    assert payload["raw_text"] == case["expected_raw_text"]
    assert payload["source_name"] == ""
    assert payload["platform"] == case["platform"]

    # 해석이 이미 낸 값은 흐름이 덮어쓰지 않는다.
    assert payload["judgment"] == interpreted_result["judgment"]
    assert payload["official_basis"] == interpreted_result["official_basis"]
    assert payload["fields"] == interpreted_result["fields"]
    assert payload["confidence"] == interpreted_result["confidence"]
    assert payload["note"] == interpreted_result["note"]


# ---------------------------------------------------------------------------
# 실기동 결함 2 — 해석이 보정 재시도까지 실패해 AdapterOutputError를 내면
# 실행 전체가 죽었다. 읽기 실패(BlockedResponseError·text 없음)와 같은
# 취급으로 그 항목만 건너뛰고 실행은 계속돼야 한다.
# ---------------------------------------------------------------------------


def test_해석이_JSON을_못_내면_그_항목만_건너뛰고_다음_항목을_계속_처리한다():
    events = [
        {"url": "https://example.com/event-1", "platform": "web"},
        {"url": "https://example.com/event-2", "platform": "web"},
    ]

    fetch_calls = []

    def fake_fetch_text(*, url):
        fetch_calls.append(url)
        return {"raw_title": "제목", "raw_text": "본문"}

    interpret_calls = []

    def fake_interpret(*, text, url, platform):
        interpret_calls.append(url)
        if url == events[0]["url"]:
            raise AdapterOutputError("could not recover JSON from adapter output")
        return _interpreted_result()

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert fetch_calls == [events[0]["url"], events[1]["url"]]
    assert interpret_calls == [events[0]["url"], events[1]["url"]]
    assert len(client.submit_event_calls) == 1
    assert client.submit_event_calls[0]["source_url"] == events[1]["url"]
    assert summary == {
        "events_attempted": 2,
        "events_failed": 1,
        "events_excluded": 0,
        "event_outcomes": [
            {"url": events[0]["url"], "outcome": "failed", "reason": "interpret_error"},
            {"url": events[1]["url"], "outcome": "created", "reason": ""},
        ],
    }


# ---------------------------------------------------------------------------
# DF-16·DF-17·DF-25·DF-18 — 해외·지난 행사는 서버에 제출하지 않고, 서버가
# 뒤늦게 제외 판정해도 실패가 아니라 제외로 센다. 국내 확정이 아닌 소스도
# 제출하지 않는다(사용자 결정: 불확실해도 제외).
# ---------------------------------------------------------------------------


class _ServerExcludesFirstEventClient(_FakeClient):
    """첫 이벤트 제출에 서버가 제외 응답을 돌려주는 가짜 클라이언트."""

    def submit_event(self, *, run_id, lease_token, event):
        self.submit_event_calls.append(event)
        return {"status": "excluded", "reason": "ended"}


class _StatusVariesClient(_FakeClient):
    """제출 응답의 status 값을 마음대로 바꿔 넣는 가짜 클라이언트."""

    def __init__(self, *, response):
        super().__init__()
        self._response = response

    def submit_event(self, *, run_id, lease_token, event):
        self.submit_event_calls.append(event)
        return self._response


def test_해외이거나_지난_행사로_판정되면_제출하지_않고_제외_수를_늘린다():
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        result = _interpreted_result()
        result["venue_country"] = "not_kr"
        return result

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert client.submit_event_calls == []
    assert summary["events_excluded"] == 1
    assert summary["events_failed"] == 0


@pytest.mark.parametrize(
    "venue_country, end_date, expected_reason",
    [
        pytest.param("not_kr", None, "overseas", id="해외"),
        pytest.param("kr", "2000-01-01", "ended", id="지난_행사"),
    ],
)
def test_현지_판정으로_제외된_이벤트는_excluded_사유로_기록된다(
    venue_country, end_date, expected_reason
):
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        result = _interpreted_result()
        result["venue_country"] = venue_country
        if end_date is not None:
            result["fields"]["end_date"] = end_date
        return result

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "excluded", "reason": expected_reason}
    ]


class _SubmitEventServerErrorClient(_FakeClient):
    """이벤트 제출에 409가 아닌 HTTP 오류(500)를 내는 가짜 클라이언트."""

    def submit_event(self, *, run_id, lease_token, event):
        self.submit_event_calls.append(event)
        raise _make_http_status_error(500)


def test_제출이_409_아닌_오류로_실패하면_failed_submit_error로_기록된다():
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        return _interpreted_result()

    client = _SubmitEventServerErrorClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "failed", "reason": "submit_error"}
    ]


@pytest.mark.parametrize(
    "server_reason, expected_reason",
    [
        pytest.param("overseas", "server_overseas", id="해외"),
        pytest.param("ended", "server_ended", id="지난_행사"),
    ],
)
def test_서버가_뒤늦게_제외하면_excluded_서버사유로_기록된다(server_reason, expected_reason):
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        return _interpreted_result()

    client = _StatusVariesClient(response={"status": "excluded", "reason": server_reason})

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "excluded", "reason": expected_reason}
    ]


@pytest.mark.parametrize(
    "server_status",
    ["created", "duplicate"],
    ids=["생성", "중복"],
)
def test_정상_제출은_created_또는_duplicate로_reason_없이_기록된다(server_status):
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        return _interpreted_result()

    client = _StatusVariesClient(response={"status": server_status, "draft_id": 1})

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": server_status, "reason": ""}
    ]


def test_이벤트_처리_로그는_결과_사유_호스트만_담고_본문은_남기지_않는다(caplog):
    events = [
        {"url": "https://empty.example.com/event-1", "platform": "web"},
        {"url": "https://ended.example.com/event-2", "platform": "web"},
        {"url": "https://ok.example.com/event-3", "platform": "web"},
    ]

    def fake_fetch_text(*, url):
        if url == events[0]["url"]:
            return None
        return {"raw_title": "비밀제목XYZ", "raw_text": "비밀본문XYZ"}

    def fake_interpret(*, text, url, platform):
        result = _interpreted_result()
        result["fields"]["title"] = "비밀제목XYZ"
        if url == events[1]["url"]:
            result["fields"]["end_date"] = "2000-01-01"
        return result

    client = _FakeClient()

    caplog.set_level(logging.INFO, logger="local_runner.exploration_flow")

    run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    records = [
        record
        for record in caplog.records
        if record.name == "local_runner.exploration_flow" and record.levelno == logging.INFO
    ]

    assert len(records) == len(events)

    expected_outcomes = ["failed", "excluded", "created"]
    for record, event, outcome in zip(records, events, expected_outcomes):
        message = record.getMessage()
        hostname = urlsplit(event["url"]).hostname
        assert outcome in message
        assert hostname in message
        assert event["url"] not in message
        assert "비밀본문XYZ" not in message
        assert "비밀제목XYZ" not in message


def test_흐름_도중_예상치_못한_예외가_나면_그때까지의_결과를_담은_예외를_던진다():
    from local_runner.exploration_flow import ExplorationFlowError

    events = [
        {"url": "https://example.com/event-1", "platform": "web"},
        {"url": "https://example.com/event-2", "platform": "web"},
    ]

    def fake_fetch_text(*, url):
        if url == events[0]["url"]:
            return None
        raise RuntimeError("boom")

    client = _FakeClient()

    with pytest.raises(ExplorationFlowError) as exc_info:
        run_exploration_flow(
            client=client,
            run_id=1,
            lease_token="tok",
            events=events,
            sources=[],
            fetch_text=fake_fetch_text,
            interpret=None,
        )

    summary = exc_info.value.summary
    assert summary["event_outcomes"] == [
        {"url": events[0]["url"], "outcome": "failed", "reason": "fetch_empty"}
    ]
    assert summary["events_attempted"] == 2
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_자정_직후에도_러너의_오늘은_UTC가_아니라_KST_날짜로_종료를_판정한다(monkeypatch):
    """UTC 2026-01-01 15:30은 KST로 2026-01-02 00:30이라 두 시간대의 오늘 날짜가
    갈린다 — end_date가 2026-01-01이면 KST 기준으로만 지난 행사다."""

    class _FrozenDatetime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 1, 15, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr("local_runner.exploration_flow.datetime", _FrozenDatetime)

    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        result = _interpreted_result()
        result["venue_country"] = "kr"
        result["fields"]["start_date"] = "2026-01-01"
        result["fields"]["end_date"] = "2026-01-01"
        return result

    client = _FakeClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert client.submit_event_calls == []
    assert summary["events_excluded"] == 1
    assert summary["events_failed"] == 0


def test_서버가_제출_응답에서_제외로_판단하면_제외_수를_늘리고_실패로_세지_않는다():
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        return _interpreted_result()

    client = _ServerExcludesFirstEventClient()

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert len(client.submit_event_calls) == 1
    assert summary["events_excluded"] == 1
    assert summary["events_failed"] == 0


@pytest.mark.parametrize(
    "response",
    [{"status": "created", "draft_id": 1}, {"draft_id": 1}],
    ids=["status_다른_값", "status_없음"],
)
def test_제출_응답의_status가_excluded가_아니면_제외로_세지_않는다(response):
    events = [{"url": "https://example.com/event-1", "platform": "web"}]

    def fake_fetch_text(*, url):
        return "원문 텍스트"

    def fake_interpret(*, text, url, platform):
        return _interpreted_result()

    client = _StatusVariesClient(response=response)

    summary = run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=events,
        sources=[],
        fetch_text=fake_fetch_text,
        interpret=fake_interpret,
    )

    assert summary["events_excluded"] == 0


def test_source_country가_kr이_아닌_소스는_제출되지_않고_kr인_소스는_그대로_제출된다():
    sources = [
        {
            "name": "국내 소스",
            "url": "https://example.com/kr",
            "source_type": "rss",
            "source_country": "kr",
        },
        {
            "name": "해외 소스",
            "url": "https://example.com/jp",
            "source_type": "rss",
            "source_country": "jp",
        },
        {
            "name": "불확실 소스",
            "url": "https://example.com/unclear",
            "source_type": "rss",
            "source_country": "unclear",
        },
        {
            # 키 자체가 없는 경우도 kr 확정이 아니므로 제외 대상이다.
            "name": "국가 미기재 소스",
            "url": "https://example.com/no-country",
            "source_type": "rss",
        },
    ]

    client = _FakeClient()

    run_exploration_flow(
        client=client,
        run_id=1,
        lease_token="tok",
        events=[],
        sources=sources,
        fetch_text=lambda *, url: None,
        interpret=lambda *, text, url, platform: None,
    )

    assert client.submit_candidate_calls == [sources[0]]
