"""local_runner.translation_flow.translate_pending_batch 단위 테스트(TR-42·
TR-42b·TR-44) — 대기 이벤트를 번역·제출하고, 거부·번역 실패·통신 오류마다
시도 횟수(attempts)를 어떻게 다루는지 검증한다. 가짜 클라이언트만 쓰고
DB·실제 HTTP·실제 claude 없음."""

import logging
import re

import httpx
import pytest

from local_runner.claude_code_adapter import AdapterOutputError
from local_runner.config import TRANSLATION_BATCH_LIMIT, TRANSLATION_MAX_ATTEMPTS
from local_runner.translation_flow import translate_pending_batch


pytestmark = pytest.mark.unit


def _대기_이벤트(event_id, source_hash="h", title="제목"):
    return {
        "event_id": event_id,
        "source_hash": source_hash,
        "fields": {"title": title, "work_title": "", "location_name": "", "summary": ""},
    }


def _고정_번역(fields):
    return {
        "en": {"title": "t", "work_title": "", "location_name": "", "summary": ""},
        "ja": {"title": "t", "work_title": "", "location_name": "", "summary": ""},
        "zh-hans": {"title": "t", "work_title": "", "location_name": "", "summary": ""},
    }


def _상태_오류(status_code):
    request = httpx.Request("POST", "https://example.com/x")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("stale_source", request=request, response=response)


def _409_오류():
    return _상태_오류(409)


class _FakeClient:
    def __init__(self, events, *, submit_exceptions=None):
        self._events = list(events)
        self.submit_calls = []
        self._submit_exceptions = submit_exceptions or {}

    def pending(self):
        return list(self._events)

    def submit(self, *, event_id, source_hash, translations):
        self.submit_calls.append((event_id, source_hash))
        exc = self._submit_exceptions.get(event_id)
        if exc is not None:
            raise exc
        return {"status": "saved", "saved": list(translations.keys()), "quarantined": {}}


class _FailingPendingClient:
    def pending(self):
        raise httpx.ConnectError("boom")


def test_대기_이벤트를_번역해_제출하고_제출_성공_수를_돌려준다():
    events = [_대기_이벤트(1), _대기_이벤트(2)]
    client = _FakeClient(events)
    translate_calls = []

    def _translate(fields):
        translate_calls.append(fields)
        return _고정_번역(fields)

    count = translate_pending_batch(client, attempts={}, translate=_translate)

    assert count == 2
    assert len(translate_calls) == 2
    assert client.submit_calls == [(1, "h"), (2, "h")]


def test_폴링_한_번에_처리하는_이벤트는_한도까지다():
    events = [_대기_이벤트(i) for i in range(1, 6)]
    client = _FakeClient(events)

    count = translate_pending_batch(client, attempts={}, translate=_고정_번역)

    assert count == TRANSLATION_BATCH_LIMIT
    assert len(client.submit_calls) == TRANSLATION_BATCH_LIMIT

    client_with_explicit_limit = _FakeClient(events)
    count_with_explicit_limit = translate_pending_batch(
        client_with_explicit_limit, attempts={}, translate=_고정_번역, limit=2
    )

    assert count_with_explicit_limit == 2


def test_한도를_주지_않으면_기본값_3건까지만_처리한다():
    events = [_대기_이벤트(i) for i in range(1, 6)]
    client = _FakeClient(events)
    translate_calls = []

    def _translate(fields):
        translate_calls.append(fields)
        return _고정_번역(fields)

    translate_pending_batch(client, attempts={}, translate=_translate)

    assert len(translate_calls) == 3


def test_시도_횟수가_한도에_도달한_이벤트는_건너뛴다():
    events = [_대기_이벤트(1, "h1"), _대기_이벤트(2, "h2")]
    client = _FakeClient(events)
    attempts = {(1, "h1"): TRANSLATION_MAX_ATTEMPTS}
    translate_calls = []

    def _translate(fields):
        translate_calls.append(fields)
        return _고정_번역(fields)

    count = translate_pending_batch(client, attempts=attempts, translate=_translate)

    assert count == 1
    assert client.submit_calls == [(2, "h2")]
    assert len(translate_calls) == 1


def test_서버가_거부하면_시도_횟수가_오르고_두_번_거부된_이벤트는_다시_시도하지_않는다():
    events = [_대기_이벤트(1, "h1")]
    key = (1, "h1")
    attempts = {}

    client_round1 = _FakeClient(events, submit_exceptions={1: _409_오류()})
    translate_pending_batch(client_round1, attempts=attempts, translate=_고정_번역)
    assert attempts[key] == 1

    client_round2 = _FakeClient(events, submit_exceptions={1: _409_오류()})
    translate_pending_batch(client_round2, attempts=attempts, translate=_고정_번역)
    assert attempts[key] == 2

    client_round3 = _FakeClient(events)
    translate_calls = []

    def _translate(fields):
        translate_calls.append(fields)
        return _고정_번역(fields)

    count = translate_pending_batch(client_round3, attempts=attempts, translate=_translate)

    assert translate_calls == []
    assert count == 0


def test_한_이벤트의_거부가_같은_배치의_다음_이벤트_처리를_막지_않는다():
    events = [_대기_이벤트(1, "h1"), _대기_이벤트(2, "h2")]
    client = _FakeClient(events, submit_exceptions={1: _409_오류()})
    attempts = {}

    count = translate_pending_batch(client, attempts=attempts, translate=_고정_번역)

    assert count == 1
    assert client.submit_calls == [(1, "h1"), (2, "h2")]
    assert attempts[(1, "h1")] == 1
    assert (2, "h2") not in attempts


def test_번역_실패도_시도_횟수를_올리고_배치를_계속한다():
    events = [_대기_이벤트(1, "h1", title="A"), _대기_이벤트(2, "h2", title="B")]
    client = _FakeClient(events)
    attempts = {}

    def _translate(fields):
        if fields["title"] == "A":
            raise AdapterOutputError("broken")
        return _고정_번역(fields)

    count = translate_pending_batch(client, attempts=attempts, translate=_translate)

    assert count == 1
    assert attempts[(1, "h1")] == 1
    assert client.submit_calls == [(2, "h2")]


def test_제출_성공이_해당_이벤트의_시도_기록을_지운다():
    events = [_대기_이벤트(1, "h1")]
    client = _FakeClient(events)
    attempts = {(1, "h1"): 1}

    translate_pending_batch(client, attempts=attempts, translate=_고정_번역)

    assert (1, "h1") not in attempts


def test_통신_오류는_시도_횟수를_올리지_않고_배치를_중단한다():
    events = [_대기_이벤트(1, "h1"), _대기_이벤트(2, "h2")]
    client = _FakeClient(events, submit_exceptions={1: httpx.ConnectError("boom")})
    attempts = {}

    with pytest.raises(httpx.ConnectError):
        translate_pending_batch(client, attempts=attempts, translate=_고정_번역)

    assert attempts == {}
    assert client.submit_calls == [(1, "h1")]


def test_pending_호출의_예외도_전파된다():
    with pytest.raises(httpx.ConnectError):
        translate_pending_batch(_FailingPendingClient(), attempts={})


@pytest.mark.parametrize("status_code", [503, 429], ids=["서버_5xx", "한도_429"])
def test_서버_오류나_한도_초과면_시도_횟수를_올리지_않고_배치를_중단한다(status_code):
    events = [_대기_이벤트(1, "h1"), _대기_이벤트(2, "h2")]
    client = _FakeClient(events, submit_exceptions={1: _상태_오류(status_code)})
    attempts = {}

    with pytest.raises(httpx.HTTPStatusError):
        translate_pending_batch(client, attempts=attempts, translate=_고정_번역)

    assert attempts == {}
    assert client.submit_calls == [(1, "h1")]


def test_번역_단계에서_ValueError가_나면_시도_횟수를_올리고_다음_이벤트를_처리한다():
    events = [_대기_이벤트(1, "h1", title="A"), _대기_이벤트(2, "h2", title="B")]
    client = _FakeClient(events)
    attempts = {}

    def _translate(fields):
        if fields["title"] == "A":
            raise ValueError("bad json")
        return _고정_번역(fields)

    count = translate_pending_batch(client, attempts=attempts, translate=_translate)

    assert count == 1
    assert attempts[(1, "h1")] == 1
    assert client.submit_calls == [(2, "h2")]


class _성공_응답_클라이언트(_FakeClient):
    def submit(self, *, event_id, source_hash, translations):
        super().submit(event_id=event_id, source_hash=source_hash, translations=translations)
        return {
            "status": "saved",
            "saved": ["en", "ja"],
            "quarantined": {"zh-hans": "wrong_script"},
        }


def test_이벤트를_제출하면_성공_로그_한_줄이_event_id와_건수만_담고_본문은_남기지_않는다(caplog):
    events = [
        _대기_이벤트(1, "h1", title="비밀제목XYZ"),
        _대기_이벤트(2, "h2", title="비밀제목XYZ"),
    ]
    client = _성공_응답_클라이언트(events)
    caplog.set_level(logging.INFO, logger="local_runner.translation_flow")

    def _translate(fields):
        translations = _고정_번역(fields)
        translations["en"]["title"] = "비밀번역문XYZ"
        return translations

    translate_pending_batch(client, attempts={}, translate=_translate)

    records = [
        r
        for r in caplog.records
        if r.name == "local_runner.translation_flow" and r.levelno == logging.INFO
    ]
    assert len(records) == 2
    first = records[0].getMessage()
    assert "event_id=1" in first
    assert re.search(r"elapsed_seconds=\d+(\.\d+)?", first)
    assert "saved=2" in first
    assert "quarantined=1" in first
    assert "비밀제목XYZ" not in caplog.text
    assert "비밀번역문XYZ" not in caplog.text


@pytest.mark.parametrize(
    "case",
    ["제출_거부_409", "번역_출력_오류"],
)
def test_이벤트_처리가_실패하면_경고_로그_한_줄이_예외_클래스와_상태코드만_담는다(case, caplog):
    caplog.set_level(logging.INFO, logger="local_runner.translation_flow")
    events = [_대기_이벤트(1, "h1")]
    if case == "제출_거부_409":
        client = _FakeClient(events, submit_exceptions={1: _409_오류()})
        translate = _고정_번역
        expected = "event_id=1 error=HTTPStatusError status=409"
    else:
        client = _FakeClient(events)

        def translate(fields):
            raise AdapterOutputError("비밀본문XYZ")

        expected = "error=AdapterOutputError status=none"

    translate_pending_batch(client, attempts={}, translate=translate)

    records = [
        r
        for r in caplog.records
        if r.name == "local_runner.translation_flow" and r.levelno == logging.WARNING
    ]
    assert len(records) == 1
    assert expected in records[0].getMessage()
    assert "비밀본문XYZ" not in caplog.text


def test_서버_오류로_배치가_중단돼도_실패_로그를_남기고_예외를_다시_던진다(caplog):
    caplog.set_level(logging.INFO, logger="local_runner.translation_flow")
    client = _FakeClient([_대기_이벤트(1, "h1")], submit_exceptions={1: _상태_오류(503)})

    with pytest.raises(httpx.HTTPStatusError):
        translate_pending_batch(client, attempts={}, translate=_고정_번역)

    records = [
        r
        for r in caplog.records
        if r.name == "local_runner.translation_flow" and r.levelno == logging.WARNING
    ]
    assert len(records) == 1
    assert "status=503" in records[0].getMessage()
