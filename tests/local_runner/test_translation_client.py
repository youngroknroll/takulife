"""local_runner.client.TranslationRunnerClient 계약 테스트(TR-39) — httpx.post
요청 경로·헤더·본문만 검증한다(대역이 실제 배선을 가리지 않도록 클라이언트를
그대로 쓴다). DB·실제 HTTP 없음."""
import logging

import httpx
import pytest

from local_runner.client import TranslationRunnerClient
from local_runner.config import RunnerConfig


pytestmark = pytest.mark.unit


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_pending은_번역_러너_경로로_토큰_헤더와_함께_요청하고_events를_돌려준다(monkeypatch):
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers})
        return _FakeResponse({"events": [{"event_id": 1, "source_hash": "h", "fields": {}}]})

    monkeypatch.setattr("local_runner.client.httpx.post", fake_post)

    config = RunnerConfig(server_url="https://example.com", runner_token="tok")
    client = TranslationRunnerClient(config)

    result = client.pending()

    assert calls[0]["url"] == "https://example.com/api/translation/runner/pending/"
    assert calls[0]["headers"] == {"X-Runner-Token": "tok"}
    assert result == [{"event_id": 1, "source_hash": "h", "fields": {}}]


def test_submit은_이벤트_id_해시_번역을_본문으로_보낸다(monkeypatch):
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append({"url": url, "json": json})
        return _FakeResponse({"status": "saved", "saved": ["en"], "quarantined": {}})

    monkeypatch.setattr("local_runner.client.httpx.post", fake_post)

    config = RunnerConfig(server_url="https://example.com", runner_token="tok")
    client = TranslationRunnerClient(config)

    translations = {
        "en": {"title": "t", "work_title": "", "location_name": "", "summary": ""},
        "ja": {"title": "t", "work_title": "", "location_name": "", "summary": ""},
        "zh-hans": {"title": "t", "work_title": "", "location_name": "", "summary": ""},
    }
    result = client.submit(event_id=5, source_hash="h5", translations=translations)

    assert calls[0]["url"] == "https://example.com/api/translation/runner/submit/"
    assert calls[0]["json"] == {
        "event_id": 5,
        "source_hash": "h5",
        "translations": translations,
    }
    assert result == {"status": "saved", "saved": ["en"], "quarantined": {}}


def test_서버가_4xx를_돌려주면_HTTPStatusError가_난다(monkeypatch):
    class _FailingResponse:
        def raise_for_status(self):
            request = httpx.Request("POST", "https://example.com/x")
            response = httpx.Response(409, request=request)
            raise httpx.HTTPStatusError("conflict", request=request, response=response)

    def fake_post(url, *, json, headers, timeout):
        return _FailingResponse()

    monkeypatch.setattr("local_runner.client.httpx.post", fake_post)

    config = RunnerConfig(server_url="https://example.com", runner_token="tok")
    client = TranslationRunnerClient(config)

    with pytest.raises(httpx.HTTPStatusError):
        client.submit(event_id=1, source_hash="h", translations={})


def test_토큰이_로그에_남지_않는다(monkeypatch, caplog):
    def fake_post(url, *, json, headers, timeout):
        return _FakeResponse({"events": []})

    monkeypatch.setattr("local_runner.client.httpx.post", fake_post)

    config = RunnerConfig(server_url="https://example.com", runner_token="super-secret-token")
    client = TranslationRunnerClient(config)

    with caplog.at_level(logging.DEBUG):
        client.pending()

    assert "super-secret-token" not in caplog.text
