"""Management command: discover_drafts

Walks enabled DraftSource rows, fetches each source's listing (RSS/sitemap/
HTML), extracts candidate event-page URLs (drafts.discovery), and creates a
PENDING EventDraft for every candidate that is not already known and is not
disallowed by robots.txt (drafts.robots) — see prompt_plan.md §2-1/§2-2/§2-5
and scratchpad pr3-test-design.md for the full design rationale.

Flag gate: DRAFT_DISCOVERY_ENABLED defaults to False (§2-5) — until an
operator turns it on this command is a no-op with a clean exit (never a
CommandError; being off is an intended, not a failure, state).

Two phases per run:
1. Listing phase (per source, isolated by try/except): robots-check the
   listing URL itself, fetch it, extract raw candidate URLs. This is also
   where `last_checked_at`/`last_error` are decided — that field reflects
   only this listing-level outcome (PO decision 3, pr3-test-design.md),
   never a later per-candidate result. A listing fetch/parse failure is a
   "real" error (counted, reported, isolated to this source) but a robots
   outcome at this level is always a normal skip. Each source's result is
   captured as an immutable `_ListingOutcome` rather than mutating a shared
   counter, so `handle()` never hands its running totals to code it does not
   control.
2. Candidate phase: every candidate collected across *all* sources in phase
   1 is deduped against EventDraft.objects (state-agnostic — a REJECTED
   draft's source_url still counts as known) in a single batch query, before
   any of them is created. Doing this as one batch (rather than re-querying
   per source) is what makes a same-run collision between two different
   sources' candidates for the same URL exercise create_draft_from_url's
   real IntegrityError -> DraftCreationDuplicateError path, instead of the
   second source's own dedup query silently absorbing it. Each surviving
   candidate then gets its own robots.txt can_fetch check (candidate paths
   are not covered by the listing URL's robots outcome) before
   create_draft_from_url is attempted, bounded by two independent budgets:
   DRAFT_DISCOVERY_MAX_PER_RUN (total creations, across every source) and
   DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE (fetch attempts — robots checks +
   create_draft_from_url calls — per source, so a source that yields mostly
   empty/duplicate candidates cannot be re-hit indefinitely while chasing
   the creation cap). A candidate removed by the dedup batch above never
   touches either budget. The per-source fetch budget and running creation
   count are inherently sequential bookkeeping (each decision depends on
   every earlier one in the same run) and stay local to `_process_candidates`;
   the per-candidate decision itself (`_decide_and_create_candidate`) takes
   that state as plain values and returns an immutable `_CandidateOutcome`
   rather than mutating anything it was handed.

Fatal vs skip (PO decision 2): a source's own listing fetch/parse failure,
and any candidate creation failure other than DraftCreationDuplicateError or
DraftCreationEmptyExtractionError, are the only "real" errors. They never
abort the run (isolated per source/candidate) but are collected and raised
as a single CommandError at the end, so a partial failure is visible to
whoever runs (or schedules) this command. robots.txt outcomes — disallowed
or fetch-failed, at either the listing or the candidate level — are always a
normal skip, never fatal.
"""
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from drafts.discovery import extract_candidate_urls
from drafts.fetching import fetch_html
from drafts.models import DraftSource, EventDraft
from drafts.robots import ROBOTS_DISALLOWED, ROBOTS_FETCH_FAILED, RobotsChecker
from drafts.services import (
    DraftCreationDuplicateError,
    DraftCreationEmptyExtractionError,
    create_draft_from_url,
)


# Small pause between per-source listing requests so a run does not hammer
# several source hosts back-to-back — a module constant (not a settings
# entry) so tests can monkeypatch time.sleep directly without needing an
# override_settings just to make the suite instant.
INTER_REQUEST_DELAY_SECONDS = 1

# rss/sitemap listings are XML, not HTML — fetch_html's default content-type
# allowlist would reject them (`allowed_content_types` *replaces* the
# default, it does not merge with it — see fetch_html's docstring). html
# listings keep fetch_html's own default by passing None through.
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

_ROBOTS_REASON_TO_SKIP_KEY = {
    ROBOTS_DISALLOWED: "robots_disallowed",
    ROBOTS_FETCH_FAILED: "robots_fetch_failed",
}


@dataclass(frozen=True)
class _ListingOutcome:
    candidate_urls: tuple = ()
    found: int = 0
    errored: bool = False
    skip_key: str = None


@dataclass(frozen=True)
class _CandidateOutcome:
    created: bool = False
    held_back: bool = False
    errored: bool = False
    consumed_fetch_budget: bool = False
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
    """Phase 1 for one source: robots-check + fetch + extract the listing.

    Persists `last_checked_at`/`last_error` as its one intentional side
    effect (that write *is* this function's contract — see module
    docstring), then returns an immutable `_ListingOutcome` describing what
    happened, rather than mutating a counter the caller owns.
    """
    listing_result = robots_checker.check(source.url)
    if not listing_result.allowed:
        skip_key = _ROBOTS_REASON_TO_SKIP_KEY[listing_result.reason]
        _mark_source_checked(source, error=f"목록 접근 불가: {listing_result.reason}")
        return _ListingOutcome(skip_key=skip_key)

    try:
        content_types = _LISTING_CONTENT_TYPES_BY_SOURCE_TYPE[source.source_type]
        content = fetch_html(source.url, allowed_content_types=content_types)
    except Exception as exc:
        # except-ok: failure is recorded on source.error and shown in the staff console
        _mark_source_checked(source, error=f"목록 fetch 실패: {exc}")
        return _ListingOutcome(errored=True)

    try:
        candidate_urls = tuple(
            extract_candidate_urls(
                source.source_type, content, source.url, selector=source.link_selector
            )
        )
    except Exception as exc:
        # except-ok: failure is recorded on source.error and shown in the staff console
        _mark_source_checked(source, error=f"목록 파싱 실패: {exc}")
        return _ListingOutcome(errored=True)

    _mark_source_checked(source, error="")
    return _ListingOutcome(candidate_urls=candidate_urls, found=len(candidate_urls))


def _process_candidates(candidates_by_source, robots_checker, stderr):
    """Phase 2, across every source's candidates at once (see module
    docstring for why this must be one batch dedup rather than per source).

    The per-source fetch budget and the running creation count are
    inherently sequential (each candidate's decision depends on every
    earlier one in this same run), so they stay as ordinary local
    bookkeeping in this one function; `_decide_and_create_candidate` itself
    receives that state as plain values and returns a new `_CandidateOutcome`
    rather than mutating anything passed in.
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
            outcome = _decide_and_create_candidate(
                source,
                url,
                already_exists=url in existing_urls,
                budget_available=fetch_budgets[source.pk] > 0,
                at_creation_cap=created_count >= settings.DRAFT_DISCOVERY_MAX_PER_RUN,
                robots_checker=robots_checker,
                stderr=stderr,
            )
            if outcome.consumed_fetch_budget:
                fetch_budgets[source.pk] -= 1
                # Etiquette pause after every candidate that actually hit
                # the network (a robots check, at minimum) — the flat floor
                # or the host's own published Crawl-delay, whichever is
                # larger. A held-back/deduped candidate never reaches here.
                time.sleep(max(INTER_REQUEST_DELAY_SECONDS, robots_checker.crawl_delay(url) or 0))
            if outcome.created:
                created_count += 1
            outcomes.append(outcome)

    return outcomes


def _decide_and_create_candidate(
    source, url, *, already_exists, budget_available, at_creation_cap, robots_checker, stderr
):
    if already_exists:
        return _CandidateOutcome(skip_key="duplicate")
    if at_creation_cap or not budget_available:
        return _CandidateOutcome(held_back=True)

    candidate_result = robots_checker.check(url)
    if not candidate_result.allowed:
        skip_key = _ROBOTS_REASON_TO_SKIP_KEY[candidate_result.reason]
        return _CandidateOutcome(consumed_fetch_budget=True, skip_key=skip_key)

    try:
        create_draft_from_url(source_url=url, source_name=source.name)
    except DraftCreationDuplicateError:
        return _CandidateOutcome(consumed_fetch_budget=True, skip_key="duplicate")
    except DraftCreationEmptyExtractionError:
        return _CandidateOutcome(consumed_fetch_budget=True, skip_key="empty")
    except Exception as exc:
        # Only the URL and the exception's class name — never str(exc),
        # which could echo back response bodies or other fetched content.
        # except-ok: reported to stderr with the exception class name only
        stderr.write(f"후보 생성 실패 {url}: {type(exc).__name__}")
        return _CandidateOutcome(consumed_fetch_budget=True, errored=True)

    return _CandidateOutcome(consumed_fetch_budget=True, created=True)


def _summarize(listing_outcomes, candidate_outcomes):
    """Pure aggregation: builds one fresh stats dict from the immutable
    outcome lists collected above — nothing here mutates an accumulator
    that was passed in from outside."""
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
