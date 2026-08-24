"""서버 소유 결정론 후보 검증 — 에이전트 보고를 신뢰하지 않고 전 단계를 재검사한다."""
import logging
import socket
import unicodedata

from django.conf import settings
from django.db import IntegrityError, transaction

from drafts.candidate_intake import (
    LISTING_CONTENT_TYPES_BY_SOURCE_TYPE,
    decide_and_create_candidate,
)
from drafts.discovery import DiscoveryParseError, extract_candidate_urls
from drafts.discovery_runs import LeaseInvalidError, locked_run_with_valid_lease, renew_lease
from drafts.extraction import EmptyExtractionError, extract_event_fields
from drafts.fetching import fetch_html
from drafts.models import DraftSource, EventDraft, SourceCandidate
from drafts.robots import RobotsChecker
from drafts.services import create_draft_from_url
from drafts.url_safety import InvalidFetchUrlError, UnsafeFetchUrlError, validate_fetch_url

logger = logging.getLogger(__name__)

# 동기 검증 fetch가 요청당 수십 초로 늘지 않게 하는 서버 강제 상한(보안 검토 g).
MAX_CANDIDATES_PER_RUN = 10

# 즉시 만드는 초기 드래프트 상한 — 전량 수집은 기존 「지금 수집」(discover_drafts)이 담당한다.
INITIAL_DRAFTS_PER_PROMOTED_SOURCE = 5

_REQUIRED_KEYS = ("name", "url", "source_type", "sample_url")
_MAX_LENGTHS = {
    "name": 100,
    "url": 200,
    "sample_url": 200,
    "link_selector": 255,
    "official_basis": 500,
    "note": 500,
}

FAILURE_MESSAGES = {
    "schema": "구조화 출력이 후보 계약을 지키지 않았다",
    "duplicate": "이미 등록된 수집처 URL이다",
    "url_safety": "URL이 안전성 검증을 통과하지 못했다",
    "robots": "robots.txt가 수집을 허용하지 않는다",
    "fetch": "목록 페이지를 가져오지 못했다",
    "listing_extraction": "선언된 유형과 선택자로 후보 URL을 추출하지 못했다",
    "sample_canary": "표본 페이지에서 규칙 기반 추출이 빈 결과를 냈다",
    "sample_mismatch": "표본 URL이 목록에서 추출된 후보가 아니다",
}


class CandidateLimitExceededError(Exception):
    pass


def sanitize_text(*, value):
    return "".join(char for char in value if unicodedata.category(char) != "Cc")


def validate_payload(*, payload):
    valid = all(key in payload for key in _REQUIRED_KEYS)

    def _string_field(key):
        nonlocal valid
        value = payload.get(key, "")
        if not isinstance(value, str):
            valid = False
            return ""
        if len(value) > _MAX_LENGTHS.get(key, len(value)):
            valid = False
        return value

    name = _string_field("name")
    url = _string_field("url")
    sample_url = _string_field("sample_url")
    link_selector = _string_field("link_selector")
    official_basis = _string_field("official_basis")
    note = _string_field("note")

    source_type = payload.get("source_type", "")
    if not isinstance(source_type, str) or source_type not in DraftSource.SourceType.values:
        valid = False
        source_type = ""

    if source_type != DraftSource.SourceType.HTML:
        link_selector = ""

    for url_value in (url, sample_url):
        if not (url_value.startswith("http://") or url_value.startswith("https://")):
            valid = False

    cleaned = {
        "name": sanitize_text(value=name)[: _MAX_LENGTHS["name"]],
        "url": sanitize_text(value=url)[: _MAX_LENGTHS["url"]],
        "source_type": source_type,
        "link_selector": sanitize_text(value=link_selector)[: _MAX_LENGTHS["link_selector"]],
        "sample_url": sanitize_text(value=sample_url)[: _MAX_LENGTHS["sample_url"]],
        "official_basis": sanitize_text(value=official_basis)[: _MAX_LENGTHS["official_basis"]],
        "note": sanitize_text(value=note)[: _MAX_LENGTHS["note"]],
    }

    return cleaned, (None if valid else "schema")


class _StderrLogAdapter:
    """decide_and_create_candidate가 요구하는 stderr.write(text) 어댑터.
    안전 문자열(URL·예외 클래스명)만 온다는 전제로 그대로 로깅한다."""

    def write(self, text):
        logger.warning("%s", text.strip())


def _save_failed_candidate(*, run_id, lease_token, cleaned, stage, exc=None):
    # 예외 클래스명만 덧붙인다 — str(exc)는 응답 본문 등 후보 원문을 그대로
    # 노출할 수 있어 절대 쓰지 않는다.
    failure_reason = FAILURE_MESSAGES[stage]
    if exc is not None:
        failure_reason = f"{failure_reason} ({type(exc).__name__})"

    with transaction.atomic():
        run = locked_run_with_valid_lease(run_id=run_id, lease_token=lease_token)
        renew_lease(run=run)
        # 조기 검사(:147) 이후 네트워크 검증(fetch·robots 등)이 진행되는 동안
        # 동시 제출들이 함께 조기 검사를 통과할 수 있어, 잠긴 run 아래에서
        # 저장 직전 한 번 더 같은 기준으로 재검사한다.
        if run.candidates.count() >= MAX_CANDIDATES_PER_RUN:
            raise CandidateLimitExceededError
        return SourceCandidate.objects.create(
            run=run,
            name=cleaned["name"],
            url=cleaned["url"],
            source_type=cleaned["source_type"],
            link_selector=cleaned["link_selector"],
            sample_url=cleaned["sample_url"],
            official_basis=cleaned["official_basis"],
            note=cleaned["note"],
            status=SourceCandidate.Status.FAILED,
            failure_stage=stage,
            failure_reason=failure_reason,
        )


def submit_candidate(*, run_id, lease_token, payload):
    url_value = payload.get("url")
    candidate_url = sanitize_text(value=url_value)[: _MAX_LENGTHS["url"]] if isinstance(url_value, str) else ""

    with transaction.atomic():
        run = locked_run_with_valid_lease(run_id=run_id, lease_token=lease_token)
        existing = run.candidates.filter(url=candidate_url).first()
        if existing is not None:
            return existing
        if run.candidates.count() >= MAX_CANDIDATES_PER_RUN:
            raise CandidateLimitExceededError

    cleaned, stage = validate_payload(payload=payload)

    if stage == "schema":
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.SCHEMA,
        )

    if DraftSource.objects.filter(url=cleaned["url"]).exists():
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.DUPLICATE,
        )

    try:
        for url in (cleaned["url"], cleaned["sample_url"]):
            validate_fetch_url(url, resolver=socket.getaddrinfo)
    except (InvalidFetchUrlError, UnsafeFetchUrlError, OSError) as exc:
        # 리졸버의 DNS 조회 실패(socket.gaierror)도 안전하지 않은 URL과 같은
        # 단계로 격리한다 — drafts/robots.py의 _ROBOTS_FETCH_FAILURES가
        # OSError를 포섭하는 것과 같은 근거.
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.URL_SAFETY,
            exc=exc,
        )

    # 이후 단계(초기 드래프트 생성)에서도 재사용할 수 있도록 인스턴스 하나만 만든다.
    robots_checker = RobotsChecker()
    for url in (cleaned["url"], cleaned["sample_url"]):
        if not robots_checker.check(url).allowed:
            return _save_failed_candidate(
                run_id=run_id,
                lease_token=lease_token,
                cleaned=cleaned,
                stage=SourceCandidate.FailureStage.ROBOTS,
            )

    try:
        listing_content = fetch_html(
            cleaned["url"],
            allowed_content_types=LISTING_CONTENT_TYPES_BY_SOURCE_TYPE[cleaned["source_type"]],
        )
    except Exception as exc:
        # except-ok: 목록 fetch 실패는 원인을 가리지 않고 전부 fetch 단계 실패다.
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.FETCH,
            exc=exc,
        )

    try:
        candidate_urls = list(
            extract_candidate_urls(
                cleaned["source_type"],
                listing_content,
                cleaned["url"],
                selector=cleaned["link_selector"],
            )
        )
    except DiscoveryParseError as exc:
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.LISTING_EXTRACTION,
            exc=exc,
        )

    if not candidate_urls:
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.LISTING_EXTRACTION,
        )

    # 아무 목록에나 남의 사이트 정상 행사 URL을 표본으로 붙여 승격을 통과시키는
    # 경로를 막는다 — 표본은 반드시 이 목록이 추출한 후보 URL이어야 한다.
    if cleaned["sample_url"] not in candidate_urls:
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.SAMPLE_MISMATCH,
        )

    try:
        sample_content = fetch_html(cleaned["sample_url"])
    except Exception as exc:
        # except-ok: 표본 fetch 실패도 목록 fetch와 같은 fetch 단계 실패다.
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.FETCH,
            exc=exc,
        )

    # canary는 추출 가능성만 확인하고 드래프트를 만들지 않는다 — 결과는 검사만
    # 하고 버린다.
    try:
        sample_fields = extract_event_fields(sample_content)
    except EmptyExtractionError as exc:
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.SAMPLE_CANARY,
            exc=exc,
        )

    if not sample_fields["raw_title"] and not sample_fields["raw_text"]:
        return _save_failed_candidate(
            run_id=run_id,
            lease_token=lease_token,
            cleaned=cleaned,
            stage=SourceCandidate.FailureStage.SAMPLE_CANARY,
        )

    with transaction.atomic():
        run = locked_run_with_valid_lease(run_id=run_id, lease_token=lease_token)
        renew_lease(run=run)
        # 실패 저장 경로(:126)와 같은 이유로, 잠긴 run 아래에서 저장 직전 한 번
        # 더 재검사한다 — 통과시켜도 결국 여기서 막히니 DraftSource 생성 시도를
        # 먼저 하지 않는다.
        if run.candidates.count() >= MAX_CANDIDATES_PER_RUN:
            raise CandidateLimitExceededError
        try:
            with transaction.atomic():
                source = DraftSource.objects.create(
                    name=cleaned["name"],
                    url=cleaned["url"],
                    source_type=cleaned["source_type"],
                    link_selector=cleaned["link_selector"],
                    enabled=True,
                )
        except IntegrityError:
            return _save_failed_candidate(
                run_id=run_id,
                lease_token=lease_token,
                cleaned=cleaned,
                stage=SourceCandidate.FailureStage.DUPLICATE,
            )

        candidate = SourceCandidate.objects.create(
            run=run,
            name=cleaned["name"],
            url=cleaned["url"],
            source_type=cleaned["source_type"],
            link_selector=cleaned["link_selector"],
            sample_url=cleaned["sample_url"],
            official_basis=cleaned["official_basis"],
            note=cleaned["note"],
            status=SourceCandidate.Status.PROMOTED,
            promoted_source=source,
        )

    existing = set(
        EventDraft.objects.filter(source_url__in=candidate_urls).values_list(
            "source_url", flat=True
        )
    )
    stderr = _StderrLogAdapter()
    created = 0
    fetches = 0
    for url in candidate_urls:
        outcome = decide_and_create_candidate(
            source,
            url,
            already_exists=url in existing,
            budget_available=fetches < settings.DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE,
            at_creation_cap=created >= INITIAL_DRAFTS_PER_PROMOTED_SOURCE,
            robots_checker=robots_checker,
            stderr=stderr,
            create_draft=create_draft_from_url,
        )
        if outcome.consumed_fetch_budget:
            fetches += 1
        if outcome.created:
            created += 1

    return candidate
