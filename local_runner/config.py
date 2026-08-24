"""러너 설정 — env에서만 읽는다(표준 라이브러리만, Django 무의존)."""
from dataclasses import dataclass
import ipaddress
import os
from urllib.parse import urlparse

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


def _is_loopback_host(hostname):
    # DNS 해석은 하지 않는다 — 신뢰 입력에 기대는 fail-fast 경로에 네트워크
    # 실패 모드를 끌어들이지 않는다. 기본은 거부.
    if hostname is None:
        return False
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return hostname.lower() == "localhost"


def _validate_server_url(server_url):
    parsed = urlparse(server_url)
    scheme = (parsed.scheme or "").lower()
    hostname = parsed.hostname

    if scheme == "https":
        return
    if scheme == "http" and _is_loopback_host(hostname):
        return
    # 비루프백 http는 러너 토큰을 평문으로 실어 보내는 사고를 막기 위해
    # 거부한다.
    raise RuntimeError("TAKULIFE_SERVER_URL must be https, or http on loopback only.")


def load_config():
    server_url = os.environ.get("TAKULIFE_SERVER_URL", "http://127.0.0.1:8000")
    runner_token = os.environ.get("TAKULIFE_RUNNER_TOKEN", "")
    if not runner_token:
        raise RuntimeError("TAKULIFE_RUNNER_TOKEN environment variable is required.")
    _validate_server_url(server_url)

    return RunnerConfig(server_url=server_url, runner_token=runner_token)
