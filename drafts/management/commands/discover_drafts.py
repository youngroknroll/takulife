"""관리 명령어: discover_drafts

활성화된 DraftSource를 순회하며 목록(RSS/사이트맵/HTML)을 가져오고, 후보 행사 URL을
추출한 뒤(drafts.discovery), 아직 모르는 URL이면서 robots.txt가 막지 않은 것만
(drafts.robots) PENDING EventDraft로 만든다.

플래그: DRAFT_DISCOVERY_ENABLED는 기본 False다. 운영자가 켜기 전까지 이 명령은
조용히 종료하며(CommandError 아님) — 꺼진 상태는 실패가 아니라 의도된 상태다.

한 번 실행에 두 단계를 거친다.
1단계(소스별): 목록 URL 자체를 robots 확인 → fetch → 후보 URL 추출. 이 단계의
   성공/실패만 source의 last_checked_at/last_error에 반영한다(이후 후보 단계 결과는
   반영하지 않는다). 목록 fetch·파싱 실패는 "진짜" 에러로 집계하지만, robots 결과는
   항상 평범한 스킵으로 취급한다. 각 소스 결과는 공유 카운터를 바꾸는 대신 불변
   _ListingOutcome으로 담는다.
2단계(후보, 전체 소스 합산): 1단계에서 모인 모든 후보를 한 번에 배치 쿼리로
   EventDraft.objects와 대조해 중복을 거른다(상태 무관 — REJECTED여도 이미 아는
   URL로 친다). 소스별로 따로 조회하지 않고 한 배치로 처리해야, 같은 실행 안에서
   서로 다른 소스가 같은 URL을 후보로 올렸을 때 실제 IntegrityError ->
   DraftCreationDuplicateError 경로를 타게 된다(두 번째 소스의 자체 dedup이
   조용히 삼키지 않는다). 살아남은 후보마다 다시 robots.txt can_fetch를 확인하고
   (목록 URL의 robots 결과는 개별 후보 경로를 대신하지 않는다), 두 가지 독립된
   상한 안에서 생성한다: DRAFT_DISCOVERY_MAX_PER_RUN(전체 생성 수)과
   DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE(소스별 fetch 시도 수 — robots 확인 +
   create_draft_from_url 호출 — 빈 결과·중복만 내는 소스가 생성 상한을 노리며
   끝없이 재시도하지 못하게 막는다). dedup에서 걸러진 후보는 두 예산 중 어느
   것도 소비하지 않는다.

에러 분류: 소스의 목록 fetch/파싱 실패, 그리고 DraftCreationDuplicateError·
DraftCreationEmptyExtractionError를 제외한 후보 생성 실패만 "진짜" 에러다. 이런
에러는 실행을 중단시키지 않고(소스/후보 단위로만 격리) 모아서 마지막에
CommandError 하나로 올려, 실행자(또는 스케줄러)가 부분 실패를 알 수 있게 한다.
robots.txt 결과(불허·fetch 실패, 목록/후보 어느 단계든)는 항상 평범한 스킵이며
절대 치명적이지 않다.
"""
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from drafts.candidate_intake import (
    CandidateOutcome,
    ROBOTS_REASON_TO_SKIP_KEY,
    decide_and_create_candidate,
)
from drafts.discovery import extract_candidate_urls
from drafts.fetching import fetch_html
from drafts.models import DraftSource, EventDraft
from drafts.robots import RobotsChecker
from drafts.services import create_draft_from_url


# 여러 소스를 연달아 두드리지 않도록 소스별 목록 요청 사이에 짧게 쉰다. 설정값이
# 아니라 모듈 상수로 둬야 테스트가 override_settings 없이 time.sleep만 몽키패치해
# 순식간에 돌릴 수 있다.
INTER_REQUEST_DELAY_SECONDS = 1

# rss/sitemap 목록은 HTML이 아니라 XML이라 fetch_html 기본 content-type
# 허용목록으로는 거부된다(allowed_content_types는 병합이 아니라 대체 — fetch_html
# 설명 참고). html 목록은 None을 넘겨 fetch_html 기본값을 그대로 쓴다.
_XML_LISTING_CONTENT_TYPES = (
    "application/xml",
    "text/xml",
    "application/rss+xml",
    "application/atom+xml",
)
_LISTING_CONTENT_TYPES_BY_SOURCE_TYPE = {
    DraftSource.SourceType.RSS: _XML_LISTING_CONTENT_TYPES,
    DraftSource.SourceType.SITEMAP: _XML_LISTING_CONTENT_TYPES,
    DraftSource.SourceType.HTML: None,
}


@dataclass(frozen=True)
class _ListingOutcome:
    candidate_urls: tuple = ()
    found: int = 0
    errored: bool = False
    skip_key: str = None


class Command(BaseCommand):
    help = "Discover new candidate event URLs from enabled DraftSource rows and create PENDING drafts."

    def handle(self, *args, **options):
        if not settings.DRAFT_DISCOVERY_ENABLED:
            self.stdout.write("DRAFT_DISCOVERY_ENABLED=False — 발견을 실행하지 않습니다.")
            return

        sources = list(DraftSource.objects.filter(enabled=True))
        if not sources:
            self.stdout.write("활성 소스가 없습니다 (enabled=True인 DraftSource: 0건)")
            return

        robots_checker = RobotsChecker()

        listing_outcomes = []
        for index, source in enumerate(sources):
            if index > 0:
                time.sleep(INTER_REQUEST_DELAY_SECONDS)
            listing_outcomes.append((source, _process_listing(source, robots_checker)))

        candidates_by_source = [
            (source, outcome.candidate_urls)
            for source, outcome in listing_outcomes
            if outcome.candidate_urls
        ]
        candidate_outcomes = _process_candidates(candidates_by_source, robots_checker, self.stderr)

        stats = _summarize(listing_outcomes, candidate_outcomes)
        self._report(stats)

        if stats["errors"]:
            raise CommandError(f"discover_drafts: {stats['errors']}건 에러 발생 — 위 로그 참고")

    def _report(self, stats):
        skipped = stats["skipped"]
        self.stdout.write(
            f"발견 {stats['found']}건 (상한 도달로 {stats['held_back']}건 보류) / 생성 {stats['created']}건"
        )
        self.stdout.write(
            "스킵 - 중복 {duplicate}건, robots 불허 {robots_disallowed}건, "
            "robots 페치 실패 {robots_fetch_failed}건, 빈 콘텐츠 {empty}건".format(**skipped)
        )
        self.stdout.write(f"에러 {stats['errors']}건")


def _mark_source_checked(source, *, error):
    source.last_checked_at = timezone.now()
    source.last_error = error
    source.save(update_fields=["last_checked_at", "last_error"])


def _process_listing(source, robots_checker):
    """소스 하나에 대한 1단계: robots 확인 + fetch + 목록 추출.

    last_checked_at/last_error를 갱신하는 것이 이 함수의 유일하고 의도된
    부작용이며(모듈 설명 참고), 결과는 호출자의 카운터를 바꾸지 않고 불변
    _ListingOutcome으로 돌려준다.
    """
    listing_result = robots_checker.check(source.url)
    if not listing_result.allowed:
        skip_key = ROBOTS_REASON_TO_SKIP_KEY[listing_result.reason]
        _mark_source_checked(source, error=f"목록 접근 불가: {listing_result.reason}")
        return _ListingOutcome(skip_key=skip_key)

    try:
        content_types = _LISTING_CONTENT_TYPES_BY_SOURCE_TYPE[source.source_type]
        content = fetch_html(source.url, allowed_content_types=content_types)
    except Exception as exc:
        # except-ok: 실패는 source.error에 기록되고 스태프 콘솔에 표시된다
        _mark_source_checked(source, error=f"목록 fetch 실패: {exc}")
        return _ListingOutcome(errored=True)

    try:
        candidate_urls = tuple(
            extract_candidate_urls(
                source.source_type, content, source.url, selector=source.link_selector
            )
        )
    except Exception as exc:
        # except-ok: 실패는 source.error에 기록되고 스태프 콘솔에 표시된다
        _mark_source_checked(source, error=f"목록 파싱 실패: {exc}")
        return _ListingOutcome(errored=True)

    _mark_source_checked(source, error="")
    return _ListingOutcome(candidate_urls=candidate_urls, found=len(candidate_urls))


def _process_candidates(candidates_by_source, robots_checker, stderr):
    """모든 소스의 후보를 한 번에 처리하는 2단계다(소스별이 아니라 한 배치여야
    하는 이유는 모듈 설명 참고).

    소스별 fetch 예산과 누적 생성 수는 본질적으로 순차적이라(각 후보의 판단이
    이 실행 안의 앞선 판단에 의존한다) 이 함수 안 지역 변수로만 관리하고,
    decide_and_create_candidate는 그 상태를 값으로만 받아 새 CandidateOutcome을
    돌려줄 뿐 아무것도 직접 바꾸지 않는다.
    """
    all_urls = [url for _source, urls in candidates_by_source for url in urls]
    if not all_urls:
        return []

    existing_urls = set(
        EventDraft.objects.filter(source_url__in=all_urls).values_list("source_url", flat=True)
    )
    fetch_budgets = {
        source.pk: settings.DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE
        for source, _urls in candidates_by_source
    }
    created_count = 0
    outcomes = []

    for source, urls in candidates_by_source:
        for url in urls:
            outcome = decide_and_create_candidate(
                source,
                url,
                already_exists=url in existing_urls,
                budget_available=fetch_budgets[source.pk] > 0,
                at_creation_cap=created_count >= settings.DRAFT_DISCOVERY_MAX_PER_RUN,
                robots_checker=robots_checker,
                stderr=stderr,
                create_draft=create_draft_from_url,
            )
            if outcome.consumed_fetch_budget:
                fetch_budgets[source.pk] -= 1
                # 네트워크를 실제로 두드린 후보마다(최소 robots 확인은 함) 예의상
                # 쉰다 — 기본 최소값과 호스트가 공표한 Crawl-delay 중 더 큰 쪽을
                # 쓴다. 보류되거나 중복 제거된 후보는 여기 오지 않는다.
                time.sleep(max(INTER_REQUEST_DELAY_SECONDS, robots_checker.crawl_delay(url) or 0))
            if outcome.created:
                created_count += 1
            outcomes.append(outcome)

    return outcomes


def _summarize(listing_outcomes, candidate_outcomes):
    """순수 집계 함수: 위에서 모은 불변 결과 목록으로 새 통계 dict를 만든다.
    외부에서 받은 누산기를 바꾸는 일은 없다."""
    listing = [outcome for _source, outcome in listing_outcomes]
    all_outcomes = listing + candidate_outcomes
    skip_keys = [outcome.skip_key for outcome in all_outcomes if outcome.skip_key]

    return {
        "found": sum(outcome.found for outcome in listing),
        "created": sum(1 for outcome in candidate_outcomes if outcome.created),
        "held_back": sum(1 for outcome in candidate_outcomes if outcome.held_back),
        "errors": sum(1 for outcome in all_outcomes if outcome.errored),
        "skipped": {
            "duplicate": skip_keys.count("duplicate"),
            "robots_disallowed": skip_keys.count("robots_disallowed"),
            "robots_fetch_failed": skip_keys.count("robots_fetch_failed"),
            "empty": skip_keys.count("empty"),
        },
    }
