"""local_runner.translation_flow.translate_pending_batch 단위 테스트(TR-42·
TR-42b·TR-44) — 대기 이벤트를 번역·제출하고, 거부·번역 실패·통신 오류마다
시도 횟수(attempts)를 어떻게 다루는지 검증한다. 가짜 클라이언트만 쓰고
DB·실제 HTTP·실제 claude 없음."""
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


def _409_오류():
    request = httpx.Request("POST", "https://example.com/x")
    response = httpx.Response(409, request=request)
    return httpx.HTTPStatusError("stale_source", request=request, response=response)


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
