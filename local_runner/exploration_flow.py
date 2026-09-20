"""탐색 결과를 받아 읽기·해석·제출로 이어주는 흐름이 여기 붙는다. events·
sources 분리·상한 절단 순수 함수와, 제출 중 임대 상실(409)을 즉시 위로
알리는 run_exploration_flow가 있다."""
import functools
import logging
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit

import httpx

from local_runner.clock import today_kst as _today_kst

logger = logging.getLogger(__name__)

# 서버의 실행당 이벤트 상한(drafts.agent_drafts.MAX_EVENTS_PER_RUN)과 같은 값이다.
EXPLORATION_MAX_EVENTS = 20
EXPLORATION_MAX_SOURCES = 10

# 서버 제외 응답의 reason(drafts.agent_drafts._exclusion_reason)만 아는 값으로
# 옮긴다 — 서버가 낼 수 없는 값이 오면 지어내지 않고 빈 사유로 남긴다.
_SERVER_EXCLUDED_REASONS = {"overseas": "server_overseas", "ended": "server_ended"}

# 탐색의 why_excluded 판정 중 우리가 코드로 재확인할 수 있는 사유만 믿고
# 건너뛴다(지난 행사는 end_date로, 해외는 소스 호스트 일치로) — 되돌리려면
# 이 집합에서 빼면 된다.
SKIPPABLE_AGENT_REASONS = frozenset({"ended", "overseas"})


def _agent_marked_ended(event, *, today):
    """탐색이 이미 지난 행사로 판정했더라도 end_date를 우리가 직접 다시
    본다 — 판정 문자열만 믿지 않는다."""
    if event.get("why_excluded") != "ended" or "ended" not in SKIPPABLE_AGENT_REASONS:
        return False
    end_date = event.get("end_date")
    if not isinstance(end_date, str):
        return False
    try:
        parsed_end_date = date.fromisoformat(end_date)
    except ValueError:
        return False
    return parsed_end_date < today


def _agent_marked_overseas(event, *, not_kr_hosts):
    """탐색이 해외로 판정한 URL의 호스트가 같은 출력의 not_kr 소스 호스트와
    실제로 겹칠 때만 믿는다 — 판정 문자열만으로는 건너뛰지 않는다."""
    if event.get("why_excluded") != "overseas" or "overseas" not in SKIPPABLE_AGENT_REASONS:
        return False
    return urlsplit(event.get("url", "")).hostname in not_kr_hosts


def _record_outcome(outcomes, *, url, outcome, reason):
    # 본문·제목·전체 URL은 로그에 남기지 않는다 — 결과·사유·호스트만 남긴다.
    outcomes.append({"url": url, "outcome": outcome, "reason": reason})
    logger.info(
        "event outcome: outcome=%s reason=%s host=%s",
        outcome,
        reason,
        urlsplit(url).hostname,
    )


class LeaseLostError(Exception):
    """제출 중 서버가 409를 냈다 — 다른 곳이 이미 이 실행의 임대를 가져갔거나
    만료돼 다시 대기 중이라는 뜻이다. 통신 오류가 아니라 흔한 경합이므로
    호출자는 이 실행 처리를 즉시 멈추고 조용히 다음 폴로 넘어가야 한다."""


class ExplorationFlowError(Exception):
    """흐름 도중 예상 못한 예외가 나도 그때까지의 결과를 완료 보고에 실어야
    한다 — 원인 예외는 __cause__로 남기고, 이 예외의 summary에 부분 결과를
    담아 호출자에게 넘긴다."""

    def __init__(self, summary):
        super().__init__("exploration flow failed before completing all items")
        self.summary = summary


def _build_summary(*, events_attempted, events_failed, events_excluded, event_outcomes):
    return {
        "events_attempted": events_attempted,
        "events_failed": events_failed,
        "events_excluded": events_excluded,
        "event_outcomes": event_outcomes,
    }


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
    from local_runner.caption_interpreter import (
        _local_precheck,
        build_interpretation_prompt,
        run_agent_interpretation,
    )

    prompt = build_interpretation_prompt(
        vocab=vocab,
        today=_today_kst().isoformat(),
        recent_drafts=[],
        text=text,
        platform=platform,
    )
    interpreted = run_agent_interpretation(prompt)
    return _local_precheck(interpreted=interpreted, source_text=text, vocab=vocab)


@dataclass(frozen=True)
class _EventContext:
    """행사 한 건 처리에 필요한 협력자·상수 묶음이다 — 값 자체는 실행 내내
    바뀌지 않는다."""

    client: object
    run_id: object
    lease_token: object
    fetch_text: object
    interpret: object
    today: object
    unknown_urls: object
    not_kr_hosts: object
    blocked_response_error: type
    expected_fetch_errors: tuple
    adapter_output_error: type
    should_submit: object
    exclusion_reason: object


@dataclass
class _FlowTally:
    """행사 루프가 도는 동안 쌓이는 카운터·기록이다 — 완료·중단 시 그대로
    요약에 실린다."""

    events_attempted: int = 0
    events_failed: int = 0
    # 제외는 실패가 아니다 — 제출 자체를 만류하거나(해외·지난 행사) 서버가
    # 뒤늦게 제외 판정한 정상 흐름이라 별도 칸으로 센다.
    events_excluded: int = 0
    # 완료 보고에 그대로 실릴 행사별 결과 목록이다.
    event_outcomes: list = field(default_factory=list)
    # 차단 응답은 명확한 신호다 — 같은 호스트를 계속 두드릴 이유가 없어
    # 첫 차단이 나는 즉시 그 호스트를 실행 내내 건너뛴다.
    blocked_hosts: set = field(default_factory=set)


def _flow_summary(tally):
    return _build_summary(
        events_attempted=tally.events_attempted,
        events_failed=tally.events_failed,
        events_excluded=tally.events_excluded,
        event_outcomes=tally.event_outcomes,
    )


def _try_skip_event(event, *, url, hostname, tally, ctx):
    """건너뛸 조건이면 카운터·기록을 남기고 True를 준다 — 호출자는 True를
    받으면 이 행사에 더 손대지 않는다."""
    if url not in ctx.unknown_urls:
        _record_outcome(tally.event_outcomes, url=url, outcome="skipped", reason="known_url")
        return True

    if _agent_marked_ended(event, today=ctx.today):
        # 차단 호스트 스킵과 대칭이다 — 건너뛴 항목도 시도·제외 수에 든다.
        tally.events_attempted += 1
        tally.events_excluded += 1
        _record_outcome(tally.event_outcomes, url=url, outcome="skipped", reason="agent_ended")
        return True

    if _agent_marked_overseas(event, not_kr_hosts=ctx.not_kr_hosts):
        tally.events_attempted += 1
        tally.events_excluded += 1
        _record_outcome(tally.event_outcomes, url=url, outcome="skipped", reason="agent_overseas")
        return True

    if hostname in tally.blocked_hosts:
        # 같은 호스트가 이미 실행 내 차단 목록에 있다 — 읽기 자체를 부르지 않는다.
        tally.events_attempted += 1
        tally.events_failed += 1
        _record_outcome(tally.event_outcomes, url=url, outcome="failed", reason="host_blocked")
        return True

    return False


def _fetch_event(*, url, hostname, tally, ctx):
    """읽기를 부르고 실패 종류별로 기록한다 — 성공하면 원문을, 실패하면
    None을 준다."""
    try:
        fetched = ctx.fetch_text(url=url)
    except ctx.blocked_response_error:
        tally.blocked_hosts.add(hostname)
        tally.events_failed += 1
        _record_outcome(tally.event_outcomes, url=url, outcome="failed", reason="blocked")
        return None
    except ctx.expected_fetch_errors as exc:
        # URL 검증·DNS·연결 오류 등 요청 전후에 흔히 나는 예외다 —
        # 이 항목만 실패로 기록하고 다음 행사로 넘어간다.
        tally.events_failed += 1
        logger.warning("event fetch failed: error=%s host=%s", type(exc).__name__, hostname)
        _record_outcome(tally.event_outcomes, url=url, outcome="failed", reason="fetch_error")
        return None

    if fetched is None:
        tally.events_failed += 1
        _record_outcome(tally.event_outcomes, url=url, outcome="failed", reason="fetch_empty")
        return None

    return fetched


def _split_fetched_text(fetched):
    # 읽기 반환 모양이 호스트마다 다르다 — 일반 웹은 {"raw_title",
    # "raw_text"} dict, 인스타 캡션은 문자열 하나다. 여기서 흡수해
    # raw_title·raw_text로 갈라 둔다.
    if isinstance(fetched, dict):
        return fetched.get("raw_title", ""), fetched.get("raw_text", "")
    return "", fetched


def _interpret_event(event, *, url, raw_title, raw_text, tally, ctx):
    """해석을 부르고 제출 가능 여부·제외 사유까지 가린다 — 제출할 값이면
    해석 결과를, 아니면 None을 준다."""
    # 해석 모델에는 제목과 본문을 한 텍스트로 합쳐 넘긴다 — 인스타 캡션은
    # 이미 한 덩어리라 그대로, 일반 웹은 제목이 본문과 분리돼 있어 모델이
    # 놓치지 않도록 앞에 붙인다.
    interpretation_text = f"{raw_title}\n{raw_text}" if raw_title else raw_text

    try:
        interpreted = ctx.interpret(text=interpretation_text, url=url, platform=event.get("platform"))
    except ctx.adapter_output_error:
        # 읽기 실패와 같은 취급이다 — 이 항목만 건너뛰고 실행 전체를 죽이지 않는다.
        tally.events_failed += 1
        _record_outcome(tally.event_outcomes, url=url, outcome="failed", reason="interpret_error")
        return None

    if not ctx.should_submit(interpreted=interpreted):
        if not interpreted.get("is_event"):
            # 해석이 행사가 아니라고 본 것은 정상 제외라 실패로 세지 않는다.
            tally.events_excluded += 1
            _record_outcome(tally.event_outcomes, url=url, outcome="excluded", reason="not_event")
        else:
            tally.events_failed += 1
            _record_outcome(tally.event_outcomes, url=url, outcome="failed", reason="no_title")
        return None

    reason = ctx.exclusion_reason(interpreted=interpreted, today=ctx.today)
    if reason is not None:
        tally.events_excluded += 1
        _record_outcome(tally.event_outcomes, url=url, outcome="excluded", reason=reason)
        return None

    return interpreted


def _submit_interpreted_event(event, *, url, raw_title, raw_text, interpreted, tally, ctx):
    """해석 결과를 서버에 제출하고 응답에 따라 기록한다 — 409는
    LeaseLostError로 곧바로 위로 던진다."""
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
        response = ctx.client.submit_event(run_id=ctx.run_id, lease_token=ctx.lease_token, event=payload)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            raise LeaseLostError("event submit returned 409") from exc
        # 캡션·페이로드 원문은 로그에 남기지 않는다 — 상태 코드와 URL만 남긴다.
        logger.warning("event submit failed: status=%s url=%s", exc.response.status_code, url)
        tally.events_failed += 1
        _record_outcome(tally.event_outcomes, url=url, outcome="failed", reason="submit_error")
        return

    if isinstance(response, dict) and response.get("status") == "excluded":
        # 앞단 필터를 통과했어도 서버가 뒤늦게 제외 판정할 수 있다.
        tally.events_excluded += 1
        server_reason = _SERVER_EXCLUDED_REASONS.get(response.get("reason"), "")
        _record_outcome(tally.event_outcomes, url=url, outcome="excluded", reason=server_reason)
    elif isinstance(response, dict) and response.get("status") in ("created", "duplicate"):
        _record_outcome(tally.event_outcomes, url=url, outcome=response["status"], reason="")


def _process_event(event, *, tally, ctx):
    """행사 한 건을 스킵 판정→읽기→해석→제출로 이어 처리한다."""
    url = event["url"]
    hostname = urlsplit(url).hostname
    if _try_skip_event(event, url=url, hostname=hostname, tally=tally, ctx=ctx):
        return

    tally.events_attempted += 1
    fetched = _fetch_event(url=url, hostname=hostname, tally=tally, ctx=ctx)
    if fetched is None:
        return

    raw_title, raw_text = _split_fetched_text(fetched)
    interpreted = _interpret_event(
        event, url=url, raw_title=raw_title, raw_text=raw_text, tally=tally, ctx=ctx
    )
    if interpreted is None:
        return

    _submit_interpreted_event(
        event,
        url=url,
        raw_title=raw_title,
        raw_text=raw_text,
        interpreted=interpreted,
        tally=tally,
        ctx=ctx,
    )


def _submit_sources(sources, *, client, run_id, lease_token, progress=None):
    """소스 후보를 국내(kr)만 골라 제출한다 — 409는 LeaseLostError로 곧바로
    위로 던진다."""
    total = len(sources)
    for index, source in enumerate(sources, start=1):
        if progress is not None:
            progress("submitting", index=index, total=total)
        # 국가가 확정된 국내(kr)가 아니면 제출하지 않는다 — 키 자체가 없거나
        # 불확실해도 제외하라는 결정이라 정규화 없이 서버와 같은 규칙을 쓴다.
        if source.get("source_country") != "kr":
            continue
        # 목록형·계정형 구분은 서버 몫이다 — 그대로 넘긴다.
        try:
            client.submit_candidate(run_id=run_id, lease_token=lease_token, candidate=source)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                raise LeaseLostError("candidate submit returned 409") from exc
            logger.warning(
                "candidate submit failed: status=%s url=%s",
                exc.response.status_code,
                source.get("url"),
            )
            continue


def _build_event_context(*, client, run_id, lease_token, events, sources, fetch_text, interpret):
    """행사 루프 시작 전 준비물을 한데 모은다 — 지연 임포트가 이 호출
    시점에 일어나야 하므로 함수 안에 그대로 둔다."""
    from local_runner.caption_interpreter import exclusion_reason, should_submit
    from local_runner.claude_code_adapter import AdapterOutputError
    from local_runner.page_fetch import (
        BlockedResponseError,
        EmptyExtractionError,
        ResponseTooLargeError,
    )
    from local_runner.url_safety import InvalidFetchUrlError, UnsafeFetchUrlError

    # 요청 전 URL 검증·DNS·연결 오류로 추정되는 예상된 읽기 예외다 — 행사
    # 하나가 이런 예외를 내도 실행 전체를 죽이지 않고 그 항목만 건너뛴다.
    expected_fetch_errors = (
        httpx.HTTPError,
        InvalidFetchUrlError,
        UnsafeFetchUrlError,
        ResponseTooLargeError,
        EmptyExtractionError,
        OSError,
    )

    urls = [event["url"] for event in events]
    unknown_urls = set(client.known_urls(urls=urls))

    # 탐색이 해외로 판정한 이벤트를 재확인할 근거다 — 같은 출력에서
    # source_country가 not_kr인 소스의 호스트만 모은다.
    not_kr_hosts = {
        urlsplit(source["url"]).hostname
        for source in sources
        if isinstance(source.get("url"), str) and source.get("source_country") == "not_kr"
    }
    not_kr_hosts.discard(None)

    return _EventContext(
        client=client,
        run_id=run_id,
        lease_token=lease_token,
        fetch_text=fetch_text,
        interpret=interpret,
        today=_today_kst(),
        unknown_urls=unknown_urls,
        not_kr_hosts=not_kr_hosts,
        blocked_response_error=BlockedResponseError,
        expected_fetch_errors=expected_fetch_errors,
        adapter_output_error=AdapterOutputError,
        should_submit=should_submit,
        exclusion_reason=exclusion_reason,
    )


def run_exploration_flow(
    *,
    client,
    run_id,
    lease_token,
    events,
    sources,
    vocab=None,
    fetch_text=None,
    interpret=None,
    progress=None,
):
    if fetch_text is None:
        fetch_text = _default_fetch_text
    if interpret is None:
        interpret = functools.partial(_default_interpret, vocab=vocab)

    ctx = _build_event_context(
        client=client,
        run_id=run_id,
        lease_token=lease_token,
        events=events,
        sources=sources,
        fetch_text=fetch_text,
        interpret=interpret,
    )
    tally = _FlowTally()

    if progress is not None:
        progress("reading", index=0, total=len(events))

    try:
        for index, event in enumerate(events, start=1):
            if progress is not None:
                progress(
                    "reading",
                    index=index,
                    total=len(events),
                    host=urlsplit(event["url"]).hostname,
                )
            _process_event(event, tally=tally, ctx=ctx)
        _submit_sources(
            sources, client=client, run_id=run_id, lease_token=lease_token, progress=progress
        )
    except LeaseLostError:
        # 다른 곳이 이미 이 실행의 임대를 가져갔다 — 부분 결과를 감싸지 않고
        # 호출자가 곧바로 조용히 다음 폴로 넘어가게 그대로 전달한다.
        raise
    except Exception as exc:
        raise ExplorationFlowError(_flow_summary(tally)) from exc

    return _flow_summary(tally)
