"""local_runner.runner 단위 테스트(U3·U4·U5) — 통신 오류 격리와 임대 상실 처리."""
import logging

import httpx
import pytest

import local_runner.runner as runner_module
from local_runner.claude_code_adapter import AdapterOutputError
from local_runner.exploration_flow import ExplorationFlowError, LeaseLostError
from local_runner.progress import ProgressReporter
from local_runner.runner import _filter_candidates, _process_run, _safe_poll


pytestmark = pytest.mark.unit


def test_제출_전_후보_목록에서_dict가_아닌_항목을_제거하고_상한으로_자른다():
    candidates = ["문자열", *[{"name": f"c{i}"} for i in range(12)], None]

    result = _filter_candidates(candidates, 10)

    assert len(result) == 10
    assert all(isinstance(item, dict) for item in result)


class _FakeClientConnectError:
    def send_heartbeat(self, provider):
        raise httpx.ConnectError("boom")


class _FakeClientHealthy:
    def send_heartbeat(self, provider):
        pass

    def claim(self):
        return None


def test_폴링_경계는_통신_오류를_격리하고_러너를_종료시키지_않는다():
    assert _safe_poll(_FakeClientConnectError()) is False
    assert _safe_poll(_FakeClientHealthy()) is True


def _make_fake_ticker_class(calls):
    class _FakeTicker:
        def __init__(self, client, interval):
            pass

        def start(self):
            calls.append(("ticker", "start"))

        def stop(self):
            calls.append(("ticker", "stop"))

    return _FakeTicker


class _OrderRecordingClient:
    def __init__(self, run, calls, submit_result=None):
        self._run = run
        self._calls = calls
        self._submit_result = submit_result

    def send_heartbeat(self, provider):
        pass

    def claim(self):
        return self._run

    def known_urls(self, *, urls):
        self._calls.append(("client", "known_urls"))
        return list(urls)

    def submit_candidate(self, *, run_id, lease_token, candidate):
        self._calls.append(("client", "submit_candidate"))
        return self._submit_result

    def complete(
        self,
        *,
        run_id,
        lease_token,
        runner_status,
        failure_kind="",
        events_attempted=0,
        events_failed=0,
        events_excluded=0,
        event_outcomes=None,
    ):
        self._calls.append(("client", "complete", runner_status, failure_kind))


def test_에이전트_탐색이_AdapterOutputError면_완료_실패_보고_이후에_heartbeat_티커가_멈춘다(monkeypatch):
    calls = []
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "query": "하츠네 미쿠",
        "vocab": {"categories": [], "regions": []},
        "existing_source_urls": [],
        "excluded_hostnames": set(),
    }
    client = _OrderRecordingClient(run, calls)

    def _raise(prompt):
        raise AdapterOutputError("could not recover JSON from adapter output")

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _make_fake_ticker_class(calls))
    monkeypatch.setattr(runner_module, "_run_exploration_agent", _raise)

    runner_module._run_once(client)

    assert calls == [
        ("ticker", "start"),
        ("client", "complete", "failed", "invalid_output"),
        ("ticker", "stop"),
    ]


class _CountingHeartbeatClient:
    def __init__(self, side_effects):
        self._side_effects = list(side_effects)
        self.calls = []
        self.on_stop = None

    def send_heartbeat(self, provider):
        self.calls.append(provider)
        effect = self._side_effects.pop(0)
        if not self._side_effects and self.on_stop is not None:
            self.on_stop()
        if isinstance(effect, Exception):
            raise effect


def test_heartbeat_전송_중_httpx_HTTPError는_기록하고_루프는_계속된다(caplog):
    client = _CountingHeartbeatClient([httpx.ConnectError("boom"), None])
    ticker = runner_module._HeartbeatTicker(client, interval=0)
    client.on_stop = ticker.stop

    with caplog.at_level(logging.WARNING, logger="local_runner.runner"):
        ticker.run()

    assert client.calls == ["claude-code", "claude-code"]
    assert "ConnectError" in caplog.text


class _RecordingHeartbeatClient:
    def __init__(self):
        self.calls = []
        self.on_call = None

    def send_heartbeat(self, provider, *, phase=None, detail=None, run_id=None):
        self.calls.append(
            {"provider": provider, "phase": phase, "detail": detail, "run_id": run_id}
        )
        if self.on_call is not None:
            self.on_call()


def test_heartbeat_티커가_progress_reporter의_현재_상태를_실어_보낸다():
    client = _RecordingHeartbeatClient()
    reporter = ProgressReporter(client, clock=lambda: 0.0)
    reporter.begin_run(7, "tok")
    reporter.set("reading", index=2, total=5, host="x.example.com")
    client.calls.clear()

    ticker = runner_module._HeartbeatTicker(client, interval=0, progress=reporter)
    client.on_call = ticker.stop

    ticker.run()

    assert client.calls == [
        {
            "provider": "claude-code",
            "phase": "reading",
            "detail": "행사 확인 중 (2/5)",
            "run_id": 7,
        }
    ]


class _BoundedHeartbeatClient:
    def __init__(self, exception, max_calls=3):
        self.calls = []
        self._exception = exception
        self._max_calls = max_calls
        self.on_max_calls = None

    def send_heartbeat(self, provider):
        self.calls.append(provider)
        if len(self.calls) >= self._max_calls and self.on_max_calls is not None:
            self.on_max_calls()
        raise self._exception


def test_heartbeat_전송_중_httpx_HTTPError가_아닌_예외는_삼키지_않고_전파한다():
    client = _BoundedHeartbeatClient(RuntimeError("bug"), max_calls=3)
    ticker = runner_module._HeartbeatTicker(client, interval=0)
    client.on_max_calls = ticker.stop  # 구코드가 계속 삼키더라도 3회에서 강제 정지 — 무한 스핀 방지 안전장치

    with pytest.raises(RuntimeError):
        ticker.run()

    assert client.calls == ["claude-code"]


def test_에이전트_탐색이_성공하면_후보_제출과_완료_보고가_끝난_뒤에야_heartbeat_티커가_멈춘다(monkeypatch):
    calls = []
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "query": "하츠네 미쿠",
        "vocab": {"categories": [], "regions": []},
        "existing_source_urls": [],
        "excluded_hostnames": set(),
    }
    client = _OrderRecordingClient(run, calls, submit_result={"status": "ok", "failure_stage": None})

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _make_fake_ticker_class(calls))
    # 이벤트 없이 소스 하나만 있는 탐색 결과로 둔다 — known_urls·submit_event
    # 배선까지 새로 흉내 내지 않아도 기존 submit_candidate 경로만으로
    # "제출 후 완료 보고" 순서를 그대로 확인할 수 있다.
    # source_country를 "kr"로 채워야 국내 필터를 통과해 제출이 실제로 일어난다.
    monkeypatch.setattr(
        runner_module,
        "_run_exploration_agent",
        lambda prompt: {"events": [], "sources": [{"name": "a", "source_country": "kr"}]},
    )

    runner_module._run_once(client)

    assert calls[-1] == ("ticker", "stop")
    assert calls.index(("ticker", "stop")) > calls.index(("client", "submit_candidate"))
    assert calls.index(("ticker", "stop")) > calls.index(("client", "complete", "succeeded", ""))


class _RecordingCompleteClient:
    def __init__(self):
        self.complete_calls = []

    def complete(
        self,
        *,
        run_id,
        lease_token,
        runner_status,
        events_attempted=0,
        events_failed=0,
        events_excluded=0,
        event_outcomes=None,
    ):
        self.complete_calls.append(
            {
                "run_id": run_id,
                "lease_token": lease_token,
                "runner_status": runner_status,
                "events_attempted": events_attempted,
                "events_failed": events_failed,
            }
        )


def test_러너_루프는_탐색_결과를_흐름_함수에_그대로_넘기고_요약을_완료_보고에_싣는다(monkeypatch):
    flow_calls = []

    def fake_run_exploration_flow(**kwargs):
        flow_calls.append(kwargs)
        return {"events_attempted": 2, "events_failed": 1}

    monkeypatch.setattr(runner_module, "run_exploration_flow", fake_run_exploration_flow)

    client = _RecordingCompleteClient()
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        # claim 응답의 어휘 — 로컬 선검사가 이걸 못 받으면 모든 카테고리·
        # 지역을 지워 버린다(코치가 찾은 결함).
        "vocab": {"categories": ["popup_store"], "regions": ["seoul"]},
    }
    exploration_result = {
        "events": [
            {"url": "https://example.com/event-1", "platform": "web"},
            {"url": "https://example.com/event-2", "platform": "web"},
        ],
        "sources": [
            {"name": "공식 홈페이지", "url": "https://example.com/feed", "source_type": "rss"}
        ],
    }

    runner_module._process_run(client, run, exploration_result)

    assert len(flow_calls) == 1
    call_kwargs = flow_calls[0]
    assert call_kwargs["client"] is client
    assert call_kwargs["run_id"] == run["run_id"]
    assert call_kwargs["lease_token"] == run["lease_token"]
    assert call_kwargs["events"] == exploration_result["events"]
    assert call_kwargs["sources"] == exploration_result["sources"]
    # claim 응답의 어휘가 그대로 흐름 함수 호출 인자에 실려 있어야 한다.
    assert call_kwargs["vocab"] == run["vocab"]

    assert client.complete_calls == [
        {
            "run_id": run["run_id"],
            "lease_token": run["lease_token"],
            "runner_status": "succeeded",
            "events_attempted": 2,
            "events_failed": 1,
        }
    ]


class _LeaseLostFlowClient:
    def __init__(self, run):
        self._run = run
        self.complete_calls = []

    def send_heartbeat(self, provider):
        pass

    def claim(self):
        return self._run

    def complete(
        self,
        *,
        run_id,
        lease_token,
        runner_status,
        failure_kind="",
        events_attempted=0,
        events_failed=0,
        events_excluded=0,
        event_outcomes=None,
    ):
        self.complete_calls.append((runner_status, failure_kind))


def test_흐름이_임대_상실을_신호하면_완료_보고_없이_조용히_끝나고_다음_폴은_실패로_집계되지_않는다(monkeypatch):
    """지금은 임대 상실이 통신 장애와 구분되지 않아 지수 백오프를 탄다.
    임대 상실은 흔한 경합이지 장애가 아니므로, 다음 폴은 정상 주기로 바로
    와야 한다."""
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "query": "하츠네 미쿠",
        "vocab": {"categories": [], "regions": []},
    }
    client = _LeaseLostFlowClient(run)

    def _raise_flow(**kwargs):
        raise LeaseLostError("lease lost")

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _make_fake_ticker_class([]))
    monkeypatch.setattr(
        runner_module,
        "_run_exploration_agent",
        lambda prompt: {"events": [], "sources": []},
    )
    monkeypatch.setattr(runner_module, "run_exploration_flow", _raise_flow)

    result = _safe_poll(client)

    assert client.complete_calls == []
    assert result is True


class _CompleteRecordingClient:
    def __init__(self, run):
        self._run = run
        self.complete_calls = []

    def send_heartbeat(self, provider):
        pass

    def claim(self):
        return self._run

    def known_urls(self, *, urls):
        return list(urls)

    def complete(
        self,
        *,
        run_id,
        lease_token,
        runner_status,
        failure_kind="",
        events_attempted=0,
        events_failed=0,
        events_excluded=0,
        event_outcomes=None,
    ):
        self.complete_calls.append(
            {
                "runner_status": runner_status,
                "failure_kind": failure_kind,
                "events_attempted": events_attempted,
                "events_failed": events_failed,
            }
        )


def test_이벤트도_소스도_없는_탐색_결과는_실패가_아니라_성공으로_완료_보고된다(monkeypatch):
    """트랙 31(계정 정기 수집)에서는 결과 0건이 오작동 신호였지만, 키워드
    탐색에서는 "이 검색어로 새 결과 없음"이 정상이라는 의미 차이를
    회귀로 고정한다."""
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "query": "하츠네 미쿠",
        "vocab": {"categories": [], "regions": []},
    }
    client = _CompleteRecordingClient(run)

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _make_fake_ticker_class([]))
    monkeypatch.setattr(
        runner_module,
        "_run_exploration_agent",
        lambda prompt: {"events": [], "sources": []},
    )

    runner_module._run_once(client)

    assert client.complete_calls == [
        {
            "runner_status": "succeeded",
            "failure_kind": "",
            "events_attempted": 0,
            "events_failed": 0,
        }
    ]


class _ExcludedRecordingCompleteClient:
    def __init__(self):
        self.complete_calls = []

    def complete(
        self,
        *,
        run_id,
        lease_token,
        runner_status,
        failure_kind="",
        events_attempted=0,
        events_failed=0,
        events_excluded=0,
        event_outcomes=None,
    ):
        self.complete_calls.append(
            {
                "run_id": run_id,
                "lease_token": lease_token,
                "runner_status": runner_status,
                "events_attempted": events_attempted,
                "events_failed": events_failed,
                "events_excluded": events_excluded,
            }
        )


def test_완료_보고에_흐름이_센_제외_수가_함께_실린다(monkeypatch):
    """흐름 요약의 events_excluded가 완료 보고 인자까지 그대로 전달돼야 한다."""

    def fake_run_exploration_flow(**kwargs):
        return {"events_attempted": 3, "events_failed": 1, "events_excluded": 2}

    monkeypatch.setattr(runner_module, "run_exploration_flow", fake_run_exploration_flow)

    client = _ExcludedRecordingCompleteClient()
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "vocab": {"categories": [], "regions": []},
    }
    exploration_result = {"events": [], "sources": []}

    runner_module._process_run(client, run, exploration_result)

    assert client.complete_calls == [
        {
            "run_id": run["run_id"],
            "lease_token": run["lease_token"],
            "runner_status": "succeeded",
            "events_attempted": 3,
            "events_failed": 1,
            "events_excluded": 2,
        }
    ]


def test_흐름에서_예상하지_못한_예외가_나면_실패로_완료_보고를_보내고_임대를_붙들지_않는다(monkeypatch):
    """실기동 결함 3 — 탐색 흐름이 임대 상실이 아닌 다른 예외로 죽으면
    완료 보고를 못 보내 실행이 claimed 상태로 남고 임대가 만료될 때까지
    다음 탐색이 막혔다. 임대 상실(LeaseLostError)만 예외로 조용히 끝내고,
    그 외 예상 못한 예외는 실패로 완료 보고를 보내 임대를 즉시 반환해야
    한다."""
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "query": "하츠네 미쿠",
        "vocab": {"categories": [], "regions": []},
    }
    client = _CompleteRecordingClient(run)

    def _raise_unexpected(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _make_fake_ticker_class([]))
    monkeypatch.setattr(
        runner_module,
        "_run_exploration_agent",
        lambda prompt: {"events": [], "sources": []},
    )
    monkeypatch.setattr(runner_module, "run_exploration_flow", _raise_unexpected)

    runner_module._run_once(client)

    assert client.complete_calls == [
        {
            "runner_status": "failed",
            "failure_kind": "exploration_error",
            "events_attempted": 0,
            "events_failed": 0,
        }
    ]


class _CompleteEventOutcomesClient:
    """완료 호출 인자를 통째로 기록만 하는 가짜 클라이언트 — event_outcomes
    배선을 검증하려는 것이라 대역이 배선을 대신 처리하면 안 된다."""

    def __init__(self):
        self.complete_calls = []

    def complete(
        self,
        *,
        run_id,
        lease_token,
        runner_status,
        failure_kind="",
        events_attempted=0,
        events_failed=0,
        events_excluded=0,
        event_outcomes=None,
    ):
        self.complete_calls.append(
            {
                "run_id": run_id,
                "lease_token": lease_token,
                "runner_status": runner_status,
                "failure_kind": failure_kind,
                "events_attempted": events_attempted,
                "events_failed": events_failed,
                "events_excluded": events_excluded,
                "event_outcomes": event_outcomes,
            }
        )


def test_탐색_흐름이_끝나면_결과_목록을_완료_보고에_싣는다(monkeypatch):
    event_outcomes = [{"url": "https://example.com/a", "outcome": "failed", "reason": "fetch_empty"}]

    def fake_run_exploration_flow(**kwargs):
        return {
            "events_attempted": 1,
            "events_failed": 1,
            "events_excluded": 0,
            "event_outcomes": event_outcomes,
        }

    monkeypatch.setattr(runner_module, "run_exploration_flow", fake_run_exploration_flow)

    client = _CompleteEventOutcomesClient()
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "vocab": {"categories": [], "regions": []},
    }
    exploration_result = {"events": [], "sources": []}

    runner_module._process_run(client, run, exploration_result)

    assert len(client.complete_calls) == 1
    call = client.complete_calls[0]
    assert call["runner_status"] == "succeeded"
    assert call["event_outcomes"] == event_outcomes


def test_탐색_흐름이_도중에_실패해도_그때까지의_결과를_실패_보고에_싣는다(monkeypatch):
    event_outcomes = [{"url": "https://example.com/a", "outcome": "failed", "reason": "fetch_empty"}]
    partial_summary = {
        "events_attempted": 1,
        "events_failed": 1,
        "events_excluded": 0,
        "event_outcomes": event_outcomes,
    }

    def fake_run_exploration_flow(**kwargs):
        raise ExplorationFlowError(partial_summary)

    monkeypatch.setattr(runner_module, "run_exploration_flow", fake_run_exploration_flow)

    client = _CompleteEventOutcomesClient()
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "vocab": {"categories": [], "regions": []},
    }
    exploration_result = {"events": [], "sources": []}

    runner_module._process_run(client, run, exploration_result)

    assert len(client.complete_calls) == 1
    call = client.complete_calls[0]
    assert call["runner_status"] == "failed"
    assert call["failure_kind"] == "exploration_error"
    assert call["event_outcomes"] == event_outcomes
    assert call["events_attempted"] == partial_summary["events_attempted"]


# ---------------------------------------------------------------------------
# TR-39 — _process_run이 실패 완료 보고를 보낼 때 원인 예외 종류를 로그로도
# 남겨야 실기동에서 무엇이 죽었는지 알 수 있다. 다만 예외 메시지 본문은
# 민감할 수 있어 로그에 남기면 안 된다(클래스명만).
# ---------------------------------------------------------------------------


def test_ExplorationFlowError의_원인_예외_클래스명이_WARNING_로그에_남고_본문은_남지_않는다(
    monkeypatch, caplog
):
    partial_summary = {
        "events_attempted": 1,
        "events_failed": 1,
        "events_excluded": 0,
        "event_outcomes": [],
    }

    def fake_run_exploration_flow(**kwargs):
        try:
            raise RuntimeError("secret-body")
        except RuntimeError as cause:
            raise ExplorationFlowError(partial_summary) from cause

    monkeypatch.setattr(runner_module, "run_exploration_flow", fake_run_exploration_flow)

    client = _CompleteEventOutcomesClient()
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "vocab": {"categories": [], "regions": []},
    }
    exploration_result = {"events": [], "sources": []}

    with caplog.at_level(logging.WARNING, logger="local_runner.runner"):
        runner_module._process_run(client, run, exploration_result)

    assert "RuntimeError" in caplog.text
    assert "secret-body" not in caplog.text


def test_예상하지_못한_일반_예외의_클래스명이_WARNING_로그에_남고_본문은_남지_않는다(
    monkeypatch, caplog
):
    def fake_run_exploration_flow(**kwargs):
        raise ValueError("secret-body-2")

    monkeypatch.setattr(runner_module, "run_exploration_flow", fake_run_exploration_flow)

    client = _CompleteEventOutcomesClient()
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "vocab": {"categories": [], "regions": []},
    }
    exploration_result = {"events": [], "sources": []}

    with caplog.at_level(logging.WARNING, logger="local_runner.runner"):
        runner_module._process_run(client, run, exploration_result)

    assert "ValueError" in caplog.text
    assert "secret-body-2" not in caplog.text


# ---------------------------------------------------------------------------
# TR-28 — S4: 러너는 탐색 프롬프트를 만들 때 local_runner.clock의 오늘(KST)을
# 그대로 전달한다.
# ---------------------------------------------------------------------------


def test_러너는_탐색_프롬프트에_clock의_오늘_날짜를_KST로_전달한다(monkeypatch):
    import datetime as datetime_module

    captured_prompts = []

    def fake_run_exploration_agent(prompt, execute=None):
        captured_prompts.append(prompt)
        return {"events": [], "sources": []}

    monkeypatch.setattr(runner_module, "today_kst", lambda: datetime_module.date(2026, 9, 18))
    monkeypatch.setattr(runner_module, "_run_exploration_agent", fake_run_exploration_agent)
    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _make_fake_ticker_class([]))

    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "query": "하츠네 미쿠",
        "vocab": {"categories": [], "regions": []},
    }
    client = _CompleteRecordingClient(run)

    runner_module._run_once(client)

    assert len(captured_prompts) == 1
    assert "2026-09-18" in captured_prompts[0]


class _ShutdownRecordingClient:
    def __init__(self):
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(("complete", kwargs))

    def send_offline(self, *, timeout):
        self.calls.append(("send_offline", timeout))


def test_진행_중에_종료하면_runner_shutdown으로_완료_보고한_뒤_오프라인을_알린다():
    from types import SimpleNamespace

    client = _ShutdownRecordingClient()
    progress = SimpleNamespace(run_id=1, lease_token="tok", last_index=2)

    runner_module._report_shutdown(client, progress)

    assert client.calls == [
        (
            "complete",
            {
                "run_id": 1,
                "lease_token": "tok",
                "runner_status": "failed",
                "failure_kind": "runner_shutdown",
                "events_attempted": 2,
            },
        ),
        ("send_offline", 3),
    ]


def test_대기_중에_종료하면_완료_보고_없이_오프라인만_알린다():
    from types import SimpleNamespace

    client = _ShutdownRecordingClient()
    progress = SimpleNamespace(run_id=None, lease_token=None, last_index=None)

    runner_module._report_shutdown(client, progress)

    assert client.calls == [("send_offline", 3)]


def _make_http_error():
    request = httpx.Request("POST", "https://example.com/x")
    response = httpx.Response(500, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


class _FailingShutdownClient:
    def __init__(self, *, fail_complete, fail_offline):
        self.calls = []
        self._fail_complete = fail_complete
        self._fail_offline = fail_offline

    def complete(self, **kwargs):
        self.calls.append("complete")
        if self._fail_complete:
            raise _make_http_error()

    def send_offline(self, *, timeout):
        self.calls.append("send_offline")
        if self._fail_offline:
            raise _make_http_error()


@pytest.mark.parametrize(
    "fail_complete, fail_offline",
    [(True, False), (False, True)],
    ids=["complete_실패", "오프라인_실패"],
)
def test_종료_보고_중_httpx_오류는_전파되지_않고_경고_로그만_남는다(fail_complete, fail_offline, caplog):
    from types import SimpleNamespace

    client = _FailingShutdownClient(fail_complete=fail_complete, fail_offline=fail_offline)
    progress = SimpleNamespace(run_id=1, lease_token="tok", last_index=2)

    with caplog.at_level(logging.WARNING, logger="local_runner.runner"):
        runner_module._report_shutdown(client, progress)

    assert client.calls == ["complete", "send_offline"]
    records = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(records) == 1
    assert "HTTPStatusError" in records[0].getMessage()
