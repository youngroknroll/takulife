"""local_runner.runner 단위 테스트(U3·U4·U5) — 통신 오류 격리와 임대 상실 처리."""
import logging

import httpx
import pytest

import local_runner.runner as runner_module
from local_runner.claude_code_adapter import AdapterOutputError
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


def _http_status_error(status_code):
    request = httpx.Request("POST", "http://testserver/x")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


class _RecordingClient:
    def __init__(self, submit_side_effects):
        self._submit_side_effects = list(submit_side_effects)
        self.submit_calls = []
        self.complete_calls = []

    def submit_candidate(self, *, run_id, lease_token, candidate):
        self.submit_calls.append(candidate)
        effect = self._submit_side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect

    def complete(self, *, run_id, lease_token, runner_status, failure_kind=""):
        self.complete_calls.append((runner_status, failure_kind))


def _make_run():
    # 서버 claim 응답의 실제 형태를 본뜬다(run_id·lease_token·max_candidates 등).
    return {"run_id": 1, "lease_token": "tok", "max_candidates": 10}


@pytest.mark.parametrize(
    "submit_side_effects,expected_submit_calls,expected_complete_calls",
    [
        ([_http_status_error(409)], 1, 0),
        (
            [_http_status_error(400), {"status": "failed", "failure_stage": "schema"}],
            2,
            1,
        ),
    ],
    ids=["임대_상실_409", "후보_거부_400"],
)
def test_임대_상실_409는_제출을_중단하고_완료_보고를_생략한다(
    submit_side_effects, expected_submit_calls, expected_complete_calls
):
    client = _RecordingClient(submit_side_effects)
    run = _make_run()
    candidates = [{"name": "a"}, {"name": "b"}]

    _process_run(client, run, candidates)

    assert len(client.submit_calls) == expected_submit_calls
    assert len(client.complete_calls) == expected_complete_calls


def test_제출_후보에_유효하지_않은_항목이_섞이면_유효한_항목은_그대로_제출하되_완료_보고는_invalid_output_실패다():
    client = _RecordingClient(
        submit_side_effects=[
            {"status": "ok", "failure_stage": None},
            {"status": "ok", "failure_stage": None},
        ]
    )
    run = _make_run()
    candidates = [{"name": "a"}, "문자열-불량", {"name": "b"}]

    _process_run(client, run, candidates)

    assert len(client.submit_calls) == 2
    assert client.complete_calls == [("failed", "invalid_output")]


def test_제출_후보가_처음부터_빈_목록이면_제출_없이_완료_보고를_invalid_output_실패로_보낸다():
    client = _RecordingClient(submit_side_effects=[])
    run = _make_run()
    candidates = []

    _process_run(client, run, candidates)

    assert client.submit_calls == []
    assert client.complete_calls == [("failed", "invalid_output")]


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

    def submit_candidate(self, *, run_id, lease_token, candidate):
        self._calls.append(("client", "submit_candidate"))
        return self._submit_result

    def complete(self, *, run_id, lease_token, runner_status, failure_kind=""):
        self._calls.append(("client", "complete", runner_status, failure_kind))


def test_에이전트_탐색이_AdapterOutputError면_완료_실패_보고_이후에_heartbeat_티커가_멈춘다(monkeypatch):
    calls = []
    run = {
        "run_id": 1,
        "lease_token": "tok",
        "max_candidates": 5,
        "existing_source_urls": [],
        "excluded_hostnames": set(),
    }
    client = _OrderRecordingClient(run, calls)

    def _raise(prompt):
        raise AdapterOutputError("could not recover JSON from adapter output")

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _make_fake_ticker_class(calls))
    monkeypatch.setattr(runner_module, "run_agent_exploration", _raise)

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
        "existing_source_urls": [],
        "excluded_hostnames": set(),
    }
    client = _OrderRecordingClient(run, calls, submit_result={"status": "ok", "failure_stage": None})

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _make_fake_ticker_class(calls))
    monkeypatch.setattr(runner_module, "run_agent_exploration", lambda prompt: [{"name": "a"}])

    runner_module._run_once(client)

    assert calls[-1] == ("ticker", "stop")
    assert calls.index(("ticker", "stop")) > calls.index(("client", "submit_candidate"))
    assert calls.index(("ticker", "stop")) > calls.index(("client", "complete", "succeeded", ""))
