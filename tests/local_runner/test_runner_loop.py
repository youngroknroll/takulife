"""local_runner.runner 단위 테스트(U3·U4·U5) — 통신 오류 격리와 임대 상실 처리."""
import httpx
import pytest

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
