"""러너 폴링 루프. 매 폴마다 heartbeat를 보내고, 임대가 있으면 에이전트 탐색을
돌려 후보를 서버에 제출한 뒤 실행을 완료 처리한다. 통신 오류·잘못된 모델
출력·임대 상실이 러너 프로세스 전체를 죽이지 않도록 각 경계에서 격리한다."""
import logging
import threading
import time

import httpx

from .claude_code_adapter import AdapterOutputError, build_prompt, run_agent_exploration
from .client import RunnerClient
from .config import POLL_INTERVAL_SECONDS, load_config

logger = logging.getLogger(__name__)

_MAX_BACKOFF_SECONDS = 300


def _failure_kind_for(exc):
    message = str(exc)
    if "timed out" in message:
        return "agent_timeout"
    if "JSON" in message or "candidates" in message:
        return "invalid_output"
    return "agent_error"


def _filter_candidates(candidates, max_candidates):
    # 서버 400 예방용 편의 필터일 뿐이다 — 최종 판정은 여전히 서버가 한다.
    return [candidate for candidate in candidates if isinstance(candidate, dict)][:max_candidates]


def _process_run(client, run, candidates):
    # 원본 후보에 dict가 아닌 항목이 섞였는지는 필터 전에 판정해둔다.
    had_invalid = any(not isinstance(c, dict) for c in candidates)
    filtered = _filter_candidates(candidates, run["max_candidates"])

    for candidate in filtered:
        try:
            result = client.submit_candidate(
                run_id=run["run_id"], lease_token=run["lease_token"], candidate=candidate
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                # 임대를 이미 잃었다 — complete를 생략하면 다음 폴에서 서버가
                # 이 실행을 재대기시키거나 만료 처리한다.
                return
            logger.warning("candidate rejected: %s status=%s", type(exc).__name__, exc.response.status_code)
            continue

        logger.info("submitted: status=%s failure_stage=%s", result.get("status"), result.get("failure_stage"))

    if had_invalid or not filtered:
        client.complete(
            run_id=run["run_id"],
            lease_token=run["lease_token"],
            runner_status="failed",
            failure_kind="invalid_output",
        )
        return

    client.complete(
        run_id=run["run_id"], lease_token=run["lease_token"], runner_status="succeeded"
    )


class _HeartbeatTicker(threading.Thread):
    """긴 에이전트 실행 동안 대시보드가 러너를 오프라인으로 오표시하지
    않도록 별도 데몬 스레드에서 계속 heartbeat를 보낸다. 통신 오류(httpx.HTTPError)는
    기록만 하고 다음 tick으로 넘어가며, 그 외 예외는 전파한다."""

    def __init__(self, client, interval):
        super().__init__(daemon=True)
        self._client = client
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.wait(self._interval):
            try:
                self._client.send_heartbeat("claude-code")
            except httpx.HTTPError as exc:
                logger.warning("heartbeat send failed: %s", type(exc).__name__)

    def stop(self):
        self._stop_event.set()


def _run_once(client):
    client.send_heartbeat("claude-code")

    run = client.claim()
    if run is None:
        return

    prompt = build_prompt(
        existing_source_urls=run["existing_source_urls"],
        excluded_hostnames=run["excluded_hostnames"],
        max_candidates=run["max_candidates"],
    )

    # 후보 제출·완료 보고가 끝날 때까지 heartbeat 티커가 살아 있어야 하므로
    # 티커 범위를 tick 종료 시점(finally)까지 넓게 잡는다.
    ticker = _HeartbeatTicker(client, POLL_INTERVAL_SECONDS)
    ticker.start()
    try:
        try:
            candidates = run_agent_exploration(prompt)
        except AdapterOutputError as exc:
            client.complete(
                run_id=run["run_id"],
                lease_token=run["lease_token"],
                runner_status="failed",
                failure_kind=_failure_kind_for(exc),
            )
            return
        _process_run(client, run, candidates)
    finally:
        ticker.stop()


def _safe_poll(client):
    try:
        _run_once(client)
    except httpx.HTTPError as exc:
        logger.warning("poll failed: %s", type(exc).__name__)
        return False
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    client = RunnerClient(config)

    consecutive_failures = 0
    try:
        while True:
            if _safe_poll(client):
                consecutive_failures = 0
                time.sleep(config.poll_interval_seconds)
            else:
                consecutive_failures += 1
                backoff = min(
                    config.poll_interval_seconds * 2**consecutive_failures,
                    _MAX_BACKOFF_SECONDS,
                )
                time.sleep(backoff)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
