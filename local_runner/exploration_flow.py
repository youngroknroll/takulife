"""탐색 결과를 받아 읽기·해석·제출로 이어주는 흐름이 여기 붙는다. 지금은
탐색 출력에서 events·sources를 분리하고 상한까지 잘라내는 순수 함수만 있다."""
from urllib.parse import urlsplit

# 서버의 실행당 이벤트 상한(drafts.agent_drafts.MAX_EVENTS_PER_RUN)과 같은 값이다.
EXPLORATION_MAX_EVENTS = 20
EXPLORATION_MAX_SOURCES = 10


def parse_exploration_output(*, data):
    events = data.get("events")
    if not isinstance(events, list):
        events = []

    sources = data.get("sources")
    if not isinstance(sources, list):
        sources = []

    return {
        "events": events[:EXPLORATION_MAX_EVENTS],
        "sources": sources[:EXPLORATION_MAX_SOURCES],
    }


def _default_fetch_text(*, url):
    from local_runner.page_fetch import fetch_event_text

    return fetch_event_text(url=url)


def _default_interpret(*, text, url, platform):
    # vocab·recent_drafts 없이 최소 기본값으로 돈다 — 이 흐름 함수 자체는
    # 아직 그 값을 받는 인자가 없다(다음 사이클이 상위 진입점에서 채운다).
    from datetime import date

    from local_runner.caption_interpreter import (
        _local_precheck,
        build_interpretation_prompt,
        run_agent_interpretation,
    )

    empty_vocab = {"categories": [], "regions": []}
    prompt = build_interpretation_prompt(
        vocab=empty_vocab,
        today=date.today().isoformat(),
        recent_drafts=[],
        text=text,
        platform=platform,
    )
    interpreted = run_agent_interpretation(prompt)
    return _local_precheck(interpreted=interpreted, source_text=text, vocab=empty_vocab)


def run_exploration_flow(
    *, client, run_id, lease_token, events, sources, fetch_text=None, interpret=None
):
    if fetch_text is None:
        fetch_text = _default_fetch_text
    if interpret is None:
        interpret = _default_interpret

    from local_runner.caption_interpreter import should_submit
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
            text = fetch_text(url=url)
        except BlockedResponseError:
            blocked_hosts.add(hostname)
            events_failed += 1
            continue

        if text is None:
            events_failed += 1
            continue

        interpreted = interpret(text=text, url=url, platform=event.get("platform"))
        if not should_submit(interpreted=interpreted):
            continue

        # 탐색이 준 platform이 해석 결과에 없으면 채운다 — judgment·official_basis는
        # 해석이 이미 낸 값을 그대로 둔다.
        payload = dict(interpreted)
        payload.setdefault("platform", event.get("platform"))
        client.submit_event(run_id=run_id, lease_token=lease_token, event=payload)

    for source in sources:
        # 목록형·계정형 구분은 서버 몫이다 — 그대로 넘긴다.
        client.submit_candidate(run_id=run_id, lease_token=lease_token, candidate=source)

    return {"events_attempted": events_attempted, "events_failed": events_failed}
