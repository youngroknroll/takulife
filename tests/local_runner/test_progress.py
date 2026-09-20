"""local_runner.progress.ProgressReporter 단위 테스트 — 5초 스로틀·phase
전이 규칙(D2)을 고정한다."""
import logging

import pytest

from local_runner.progress import ProgressReporter


pytestmark = pytest.mark.unit


class _FakeClient:
    def __init__(self):
        self.sent = []

    def send_heartbeat(self, provider, *, phase=None, detail=None, run_id=None):
        self.sent.append({"phase": phase, "detail": detail, "run_id": run_id})


def _fake_clock(values):
    values = list(values)

    def clock():
        return values.pop(0)

    return clock


def test_같은_phase에서_5초가_지나기_전에_detail이_바뀌면_전송은_보류되고_로그는_남는다(caplog):
    client = _FakeClient()
    clock = _fake_clock([0.0, 2.0])
    reporter = ProgressReporter(client, clock=clock)
    reporter.begin_run(7, "tok")
    reporter.set("reading", index=1, total=3, host="a.example.com")
    client.sent.clear()
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="local_runner.progress"):
        reporter.set("reading", index=2, total=3, host="a.example.com")

    assert client.sent == []
    records = [record for record in caplog.records if record.levelno == logging.INFO]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "행사 확인 중 (2/3)" in message
    assert "a.example.com" in message


def test_같은_phase에서_5초_이상_지나_detail이_바뀌면_즉시_heartbeat_1회가_난다():
    client = _FakeClient()
    clock = _fake_clock([0.0, 5.5])
    reporter = ProgressReporter(client, clock=clock)
    reporter.begin_run(7, "tok")
    reporter.set("reading", index=1, total=3, host="a.example.com")
    client.sent.clear()

    reporter.set("reading", index=2, total=3, host="a.example.com")

    assert client.sent == [{"phase": "reading", "detail": "행사 확인 중 (2/3)", "run_id": 7}]


def test_phase가_바뀌면_5초가_지나지_않았어도_즉시_heartbeat가_난다():
    client = _FakeClient()
    clock = _fake_clock([0.0, 1.0])
    reporter = ProgressReporter(client, clock=clock)
    reporter.begin_run(7, "tok")
    reporter.set("reading", index=3, total=3)
    client.sent.clear()

    reporter.set("submitting", index=0, total=2)

    assert client.sent == [{"phase": "submitting", "detail": "소스 후보 제출 중 (0/2)", "run_id": 7}]
