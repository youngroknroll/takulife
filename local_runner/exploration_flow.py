"""탐색 결과를 받아 읽기·해석·제출로 이어주는 흐름이 여기 붙는다. 지금은
탐색 출력에서 events·sources를 분리하고 상한까지 잘라내는 순수 함수만 있다."""

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
