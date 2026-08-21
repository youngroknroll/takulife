"""httpx 기반 러너 API 클라이언트. 토큰·응답 원문은 어디에도 print/log하지 않는다."""
import httpx

_TIMEOUT_SECONDS = 30
_RUNNER_URL_PREFIX = "/api/discovery/runner"


class RunnerClient:
    def __init__(self, config):
        self._config = config
        self._headers = {"X-Runner-Token": config.runner_token}

    def _post(self, path, json_body):
        response = httpx.post(
            f"{self._config.server_url}{_RUNNER_URL_PREFIX}{path}",
            json=json_body,
            headers=self._headers,
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response

    def send_heartbeat(self, provider):
        self._post("/heartbeat/", {"provider": provider})

    def claim(self):
        response = self._post("/claim/", {"provider": "claude-code"})
        return response.json()["run"]

    def submit_candidate(self, *, run_id, lease_token, candidate):
        response = self._post(
            f"/runs/{run_id}/candidates/",
            {"lease_token": lease_token, "candidate": candidate},
        )
        return response.json()

    def complete(self, *, run_id, lease_token, runner_status, failure_kind=""):
        response = self._post(
            f"/runs/{run_id}/complete/",
            {
                "lease_token": lease_token,
                "runner_status": runner_status,
                "failure_kind": failure_kind,
            },
        )
        return response.json()
