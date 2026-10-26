"""local_runner.runner._safe_translate와 main() 배선 단위 테스트(TR-40·TR-43) —
번역 단계 실패가 폴링 루프를 멈추지 않는지, 폴링 성공 후에만 번역 단계가
도는지 확인한다. _make_fake_ticker_class 등 기존 test_runner_loop.py의
가짜 객체 관례를 따른다. DB·실제 HTTP·실제 claude 없음."""
import httpx
import pytest

import local_runner.runner as runner_module
from local_runner.claude_code_adapter import AdapterOutputError


pytestmark = pytest.mark.unit


def _성공_번역(translation_client, attempts, progress=None):
    return 1


# ---------------------------------------------------------------------------
# TR-40 — 번역 단계 실패(통신 오류·출력 오류)가 폴링 루프를 멈추지 않는다.
# KeyboardInterrupt는 삼키지 않는다.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exception",
    [
        httpx.ConnectError("boom"),
        AdapterOutputError("broken"),
        ValueError("not json"),
        KeyError("events"),
    ],
    ids=["통신_오류", "출력_오류", "JSON_아님", "응답_키_없음"],
)
def test_번역_단계_실패가_폴링_루프를_멈추지_않는다(exception, monkeypatch):
    def _raise(translation_client, attempts, progress=None):
        raise exception

    monkeypatch.setattr(runner_module, "translate_pending_batch", _raise)

    result = runner_module._safe_translate(object(), {})

    assert result is False


def test_번역_단계_성공은_True를_돌려준다(monkeypatch):
    monkeypatch.setattr(runner_module, "translate_pending_batch", _성공_번역)

    result = runner_module._safe_translate(object(), {})

    assert result is True


def test_KeyboardInterrupt는_삼키지_않는다(monkeypatch):
    def _raise(translation_client, attempts, progress=None):
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner_module, "translate_pending_batch", _raise)

    with pytest.raises(KeyboardInterrupt):
        runner_module._safe_translate(object(), {})


# ---------------------------------------------------------------------------
# TR-43 — 번역 단계는 하트비트 티커 안에서 돌고, 실패해도 티커를 멈춘다.
# ---------------------------------------------------------------------------


def _기록하는_가짜_티커_클래스(calls):
    class _FakeTicker:
        def __init__(self, client, interval, progress=None):
            pass

        def start(self):
            calls.append(("ticker", "start"))

        def stop(self):
            calls.append(("ticker", "stop"))

    return _FakeTicker


def test_번역_단계는_하트비트_티커_안에서_돌고_성공하면_순서대로_멈춘다(monkeypatch):
    calls = []

    def _translate(translation_client, attempts, progress=None):
        calls.append(("translate",))
        return 1

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _기록하는_가짜_티커_클래스(calls))
    monkeypatch.setattr(runner_module, "translate_pending_batch", _translate)

    result = runner_module._safe_translate(object(), {})

    assert result is True
    assert calls == [("ticker", "start"), ("translate",), ("ticker", "stop")]


def test_번역_단계는_실패해도_하트비트_티커를_멈춘다(monkeypatch):
    calls = []

    def _translate(translation_client, attempts, progress=None):
        calls.append(("translate",))
        raise AdapterOutputError("broken")

    monkeypatch.setattr(runner_module, "_HeartbeatTicker", _기록하는_가짜_티커_클래스(calls))
    monkeypatch.setattr(runner_module, "translate_pending_batch", _translate)

    result = runner_module._safe_translate(object(), {})

    assert result is False
    assert calls == [("ticker", "start"), ("translate",), ("ticker", "stop")]


# ---------------------------------------------------------------------------
# main() 배선 — 폴링이 성공한 반복에서만 번역 단계를 한 번 돌린다.
# ---------------------------------------------------------------------------


class _FakeConfig:
    poll_interval_seconds = 20


class _FakeClient:
    pass


class _FakeTranslationClient:
    pass


class _FakeProgress:
    def heartbeat(self):
        pass


def _main_배선_공통_패치(monkeypatch, *, safe_poll_result, calls):
    def fake_safe_poll(client, progress=None):
        calls.append("poll")
        return safe_poll_result

    def fake_safe_translate(translation_client, attempts, progress=None):
        calls.append("translate")
        return True

    def fake_sleep(seconds):
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner_module, "load_config", lambda: _FakeConfig())
    monkeypatch.setattr(runner_module, "RunnerClient", lambda config: _FakeClient())
    monkeypatch.setattr(
        runner_module, "TranslationRunnerClient", lambda config: _FakeTranslationClient()
    )
    monkeypatch.setattr(runner_module, "ProgressReporter", lambda client: _FakeProgress())
    monkeypatch.setattr(runner_module, "_report_shutdown", lambda client, progress: None)
    monkeypatch.setattr(runner_module, "_safe_poll", fake_safe_poll)
    monkeypatch.setattr(runner_module, "_safe_translate", fake_safe_translate)
    monkeypatch.setattr(runner_module.time, "sleep", fake_sleep)


def test_main_배선_폴링이_성공하면_번역_단계가_한_번_돈다(monkeypatch):
    calls = []
    _main_배선_공통_패치(monkeypatch, safe_poll_result=True, calls=calls)

    runner_module.main()

    assert calls == ["poll", "translate"]


def test_main_배선_폴링이_실패하면_번역_단계를_건너뛴다(monkeypatch):
    calls = []
    _main_배선_공통_패치(monkeypatch, safe_poll_result=False, calls=calls)

    runner_module.main()

    assert calls == ["poll"]
