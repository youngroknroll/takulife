"""local_runner.client 계약 테스트 — httpx.post 요청 본문만 검증한다(대역이
실제 배선을 가리지 않도록 RunnerClient를 그대로 쓴다)."""
import pytest

from local_runner.client import RunnerClient
from local_runner.config import RunnerConfig


pytestmark = pytest.mark.unit


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"status": "succeeded"}


def test_RunnerClient_complete는_event_outcomes를_요청_본문에_담아_보낸다(monkeypatch):
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append(json)
        return _FakeResponse()

    monkeypatch.setattr("local_runner.client.httpx.post", fake_post)

    config = RunnerConfig(server_url="https://example.com", runner_token="tok")
    client = RunnerClient(config)

    event_outcomes = [{"url": "https://example.com/a", "outcome": "failed", "reason": "fetch_empty"}]

    client.complete(
        run_id=1,
        lease_token="t",
        runner_status="succeeded",
        event_outcomes=event_outcomes,
    )

    assert calls[0]["event_outcomes"] == event_outcomes
