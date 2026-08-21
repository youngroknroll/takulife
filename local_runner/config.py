"""러너 설정 — env에서만 읽는다(표준 라이브러리만, Django 무의존)."""
from dataclasses import dataclass
import os

# 서버가 러너에게 임대를 내주는 폴링 주기(초).
POLL_INTERVAL_SECONDS = 20
# 에이전트 웹 탐색 1회에 허용하는 최대 시간(초).
AGENT_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class RunnerConfig:
    server_url: str
    runner_token: str
    poll_interval_seconds: int = POLL_INTERVAL_SECONDS
    agent_timeout_seconds: int = AGENT_TIMEOUT_SECONDS


def load_config():
    server_url = os.environ.get("TAKULIFE_SERVER_URL", "http://127.0.0.1:8000")
    runner_token = os.environ.get("TAKULIFE_RUNNER_TOKEN", "")
    if not runner_token:
        raise RuntimeError("TAKULIFE_RUNNER_TOKEN environment variable is required.")

    return RunnerConfig(server_url=server_url, runner_token=runner_token)
