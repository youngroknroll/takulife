"""러너 폴링 루프. 매 폴마다 heartbeat를 보내고, 임대가 있으면 에이전트 탐색을
돌려 이벤트·소스를 서버에 제출한 뒤 실행을 완료 처리한다. 통신 오류·잘못된
모델 출력·임대 상실이 러너 프로세스 전체를 죽이지 않도록 각 경계에서
격리한다."""
import functools
import logging
import threading
import time

import httpx

from .claude_code_adapter import (
    AdapterOutputError,
    _CORRECTION_SUFFIX,
    _execute_claude,
    build_exploration_prompt,
    parse_json_object,
)
from .client import RunnerClient
from .config import POLL_INTERVAL_SECONDS, load_config
from .exploration_flow import (
    EXPLORATION_MAX_EVENTS,
    EXPLORATION_MAX_SOURCES,
    LeaseLostError,
    parse_exploration_output,
    run_exploration_flow,
)

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


def _run_exploration_agent(prompt, execute=None):
    # run_agent_exploration(claude_code_adapter.py)은 후보 목록 스키마
    # ({"candidates": [...]})용으로 이미 테스트가 고정돼 있어 그대로 재사용할
    # 수 없다 — 탐색 출력은 이제 {"events": [...], "sources": [...]} 단일
    # 객체라 parse_json_object로 받아야 한다. 실행·재시도 구조만 그대로 복제한다.
    if execute is None:
        execute = functools.partial(_execute_claude, tools="WebSearch,WebFetch", strict_mcp=True)

    output = execute(prompt)
    try:
        return parse_json_object(output)
    except AdapterOutputError:
        pass

    corrected_output = execute(f"{prompt}\n\n{_CORRECTION_SUFFIX}")
    return parse_json_object(corrected_output)


def _process_run(client, run, exploration_result):
    # 얇은 배선이다 — 판단 로직은 run_exploration_flow가 갖고 있다.
    try:
        summary = run_exploration_flow(
            client=client,
            run_id=run["run_id"],
            lease_token=run["lease_token"],
            events=exploration_result["events"],
            sources=exploration_result["sources"],
            vocab=run["vocab"],
        )
    except LeaseLostError:
        # 임대 상실은 다른 곳이 이미 이 실행을 가져갔거나 만료돼 다시
        # 대기 중이라는 뜻이다 — 흔한 경합이지 장애가 아니다. 완료 보고를
        # 부르지 않고 조용히 돌아온다. 통신 오류로 취급해 다시 던지면
        # _safe_poll이 실패로 집계해 다음 폴을 불필요하게 늦춘다.
        return
    client.complete(
        run_id=run["run_id"],
        lease_token=run["lease_token"],
        runner_status="succeeded",
        events_attempted=summary["events_attempted"],
        events_failed=summary["events_failed"],
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

    prompt = build_exploration_prompt(
        query=run["query"],
        max_events=EXPLORATION_MAX_EVENTS,
        max_sources=EXPLORATION_MAX_SOURCES,
    )

    # 이벤트·소스 제출·완료 보고가 끝날 때까지 heartbeat 티커가 살아 있어야
    # 하므로 티커 범위를 tick 종료 시점(finally)까지 넓게 잡는다.
    ticker = _HeartbeatTicker(client, POLL_INTERVAL_SECONDS)
    ticker.start()
    try:
        try:
            raw_output = _run_exploration_agent(prompt)
        except AdapterOutputError as exc:
            client.complete(
                run_id=run["run_id"],
                lease_token=run["lease_token"],
                runner_status="failed",
                failure_kind=_failure_kind_for(exc),
            )
            return
        exploration_result = parse_exploration_output(data=raw_output)
        _process_run(client, run, exploration_result)
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
