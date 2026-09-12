"""local_runner.runner 단위 테스트(U3·U4·U5) — 통신 오류 격리와 임대 상실 처리."""
import logging

import httpx
import pytest

import local_runner.runner as runner_module
from local_runner.claude_code_adapter import AdapterOutputError
from local_runner.exploration_flow import LeaseLostError
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

    def complete(self, *, run_id, lease_token, runner_status, failure_kind="", events_attempted=0, events_failed=0):
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
    monkeypatch.setattr(
        runner_module,
        "_run_exploration_agent",
        lambda prompt: {"events": [], "sources": [{"name": "a"}]},
    )

    runner_module._run_once(client)

    assert calls[-1] == ("ticker", "stop")
    assert calls.index(("ticker", "stop")) > calls.index(("client", "submit_candidate"))
    assert calls.index(("ticker", "stop")) > calls.index(("client", "complete", "succeeded", ""))


class _RecordingCompleteClient:
    def __init__(self):
        self.complete_calls = []

    def complete(self, *, run_id, lease_token, runner_status, events_attempted=0, events_failed=0):
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

    def complete(self, *, run_id, lease_token, runner_status, failure_kind="", events_attempted=0, events_failed=0):
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

    def complete(self, *, run_id, lease_token, runner_status, failure_kind="", events_attempted=0, events_failed=0):
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
