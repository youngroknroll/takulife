"""러너 폴링 루프. 매 폴마다 heartbeat를 보내고, 임대가 있으면 에이전트 탐색을
돌려 후보를 서버에 제출한 뒤 실행을 완료 처리한다."""
import time

from .claude_code_adapter import AdapterOutputError, build_prompt, run_agent_exploration
from .client import RunnerClient
from .config import load_config


def _failure_kind_for(exc):
    message = str(exc)
    if "timed out" in message:
        return "agent_timeout"
    if "JSON" in message or "candidates" in message:
        return "invalid_output"
    return "agent_error"


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

    for candidate in candidates:
        result = client.submit_candidate(
            run_id=run["run_id"], lease_token=run["lease_token"], candidate=candidate
        )
        print(f"submitted: status={result.get('status')} failure_stage={result.get('failure_stage')}")

    client.complete(
        run_id=run["run_id"], lease_token=run["lease_token"], runner_status="succeeded"
    )


def main():
    config = load_config()
    client = RunnerClient(config)

    try:
        while True:
            _run_once(client)
            time.sleep(config.poll_interval_seconds)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
