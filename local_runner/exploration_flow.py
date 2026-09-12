"""탐색 결과를 받아 읽기·해석·제출로 이어주는 흐름이 여기 붙는다. events·
sources 분리·상한 절단 순수 함수와, 제출 중 임대 상실(409)을 즉시 위로
알리는 run_exploration_flow가 있다."""
import functools
import logging
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

# 서버의 실행당 이벤트 상한(drafts.agent_drafts.MAX_EVENTS_PER_RUN)과 같은 값이다.
EXPLORATION_MAX_EVENTS = 20
EXPLORATION_MAX_SOURCES = 10


class LeaseLostError(Exception):
    """제출 중 서버가 409를 냈다 — 다른 곳이 이미 이 실행의 임대를 가져갔거나
    만료돼 다시 대기 중이라는 뜻이다. 통신 오류가 아니라 흔한 경합이므로
    호출자는 이 실행 처리를 즉시 멈추고 조용히 다음 폴로 넘어가야 한다."""


def parse_exploration_output(*, data):
    events = data.get("events")
    if not isinstance(events, list):
        events = []
    events = [event for event in events if isinstance(event, dict)]

    sources = data.get("sources")
    if not isinstance(sources, list):
        sources = []
    sources = [source for source in sources if isinstance(source, dict)]

    return {
        "events": events[:EXPLORATION_MAX_EVENTS],
        "sources": sources[:EXPLORATION_MAX_SOURCES],
    }


def _default_fetch_text(*, url):
    from local_runner.page_fetch import fetch_event_text

    return fetch_event_text(url=url)


def _default_interpret(*, text, url, platform, vocab):
    # recent_drafts는 claim 응답에 실려 오지 않아 빈 목록으로 둔다(보고 대상 —
    # 지어내지 않는다). vocab만은 호출자가 claim 응답에서 꺼내 반드시 넘긴다 —
    # 비워 두면 로컬 선검사가 모든 카테고리·지역을 지워 버린다.
    from datetime import date

    from local_runner.caption_interpreter import (
        _local_precheck,
        build_interpretation_prompt,
        run_agent_interpretation,
    )

    prompt = build_interpretation_prompt(
        vocab=vocab,
        today=date.today().isoformat(),
        recent_drafts=[],
        text=text,
        platform=platform,
    )
    interpreted = run_agent_interpretation(prompt)
    return _local_precheck(interpreted=interpreted, source_text=text, vocab=vocab)


def run_exploration_flow(
    *, client, run_id, lease_token, events, sources, vocab=None, fetch_text=None, interpret=None
):
    if fetch_text is None:
        fetch_text = _default_fetch_text
    if interpret is None:
        interpret = functools.partial(_default_interpret, vocab=vocab)

    from local_runner.caption_interpreter import should_submit
    from local_runner.claude_code_adapter import AdapterOutputError
    from local_runner.page_fetch import BlockedResponseError

    urls = [event["url"] for event in events]
    unknown_urls = set(client.known_urls(urls=urls))

    events_attempted = 0
    events_failed = 0
    # 차단 응답은 명확한 신호다 — 같은 호스트를 계속 두드릴 이유가 없어
    # 첫 차단이 나는 즉시 그 호스트를 실행 내내 건너뛴다.
    blocked_hosts = set()

    for event in events:
        url = event["url"]
        if url not in unknown_urls:
            continue

        hostname = urlsplit(url).hostname
        if hostname in blocked_hosts:
            # 같은 호스트가 이미 실행 내 차단 목록에 있다 — 읽기 자체를
            # 부르지 않는다.
            events_attempted += 1
            events_failed += 1
            continue

        events_attempted += 1
        try:
            fetched = fetch_text(url=url)
        except BlockedResponseError:
            blocked_hosts.add(hostname)
            events_failed += 1
            continue

        if fetched is None:
            events_failed += 1
            continue

        # 읽기 반환 모양이 호스트마다 다르다 — 일반 웹은 {"raw_title",
        # "raw_text"} dict, 인스타 캡션은 문자열 하나다. 여기서 흡수해
        # raw_title·raw_text로 갈라 둔다.
        if isinstance(fetched, dict):
            raw_title = fetched.get("raw_title", "")
            raw_text = fetched.get("raw_text", "")
        else:
            raw_title = ""
            raw_text = fetched

        # 해석 모델에는 제목과 본문을 한 텍스트로 합쳐 넘긴다 — 인스타 캡션은
        # 이미 한 덩어리라 그대로, 일반 웹은 제목이 본문과 분리돼 있어 모델이
        # 놓치지 않도록 앞에 붙인다.
        interpretation_text = f"{raw_title}\n{raw_text}" if raw_title else raw_text

        try:
            interpreted = interpret(
                text=interpretation_text, url=url, platform=event.get("platform")
            )
        except AdapterOutputError:
            # 읽기 실패와 같은 취급이다 — 이 항목만 건너뛰고 실행 전체를
            # 죽이지 않는다.
            events_failed += 1
            continue

        if not should_submit(interpreted=interpreted):
            continue

        # 탐색이 준 platform이 해석 결과에 없으면 채운다 — judgment·official_basis는
        # 해석이 이미 낸 값을 그대로 둔다.
        payload = dict(interpreted)
        payload.setdefault("platform", event.get("platform"))
        # 해석 모델은 주소·원문·출처명을 모른다 — 흐름이 아는 값을 채운다.
        payload.setdefault("source_url", url)
        payload.setdefault("raw_title", raw_title)
        payload.setdefault("raw_text", raw_text)
        # 공식 채널명을 확인할 근거가 없다 — 검색어를 넣지 말라는 계획
        # 제약과 같은 이유로 지어내는 대신 비워 둔다(검수 화면은 빈
        # source_name을 이미 정상 상태로 다룬다).
        payload.setdefault("source_name", "")
        try:
            client.submit_event(run_id=run_id, lease_token=lease_token, event=payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                raise LeaseLostError("event submit returned 409") from exc
            # 캡션·페이로드 원문은 로그에 남기지 않는다 — 상태 코드와 URL만 남긴다.
            logger.warning("event submit failed: status=%s url=%s", exc.response.status_code, url)
            events_failed += 1
            continue

    for source in sources:
        # 목록형·계정형 구분은 서버 몫이다 — 그대로 넘긴다.
        try:
            client.submit_candidate(run_id=run_id, lease_token=lease_token, candidate=source)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                raise LeaseLostError("candidate submit returned 409") from exc
            logger.warning(
                "candidate submit failed: status=%s url=%s", exc.response.status_code, source.get("url")
            )
            continue

    return {"events_attempted": events_attempted, "events_failed": events_failed}
