# 후보 URL 하나를 검토해 EventDraft로 만들지 판단하는 로직이다. discover_drafts
# 명령과 곧 추가될 후보 승격 경로가 같은 robots 재검증·중복·생성 규칙을 공유해야
# 해서 명령 모듈 밖으로 뺐다.
from dataclasses import dataclass

from drafts.models import DraftSource
from drafts.robots import ROBOTS_DISALLOWED, ROBOTS_FETCH_FAILED
from drafts.services import DraftCreationDuplicateError, DraftCreationEmptyExtractionError

ROBOTS_REASON_TO_SKIP_KEY = {
    ROBOTS_DISALLOWED: "robots_disallowed",
    ROBOTS_FETCH_FAILED: "robots_fetch_failed",
}

# rss/sitemap 목록은 HTML이 아니라 XML이라 fetch_html 기본 content-type
# 허용목록으로는 거부된다(allowed_content_types는 병합이 아니라 대체 — fetch_html
# 설명 참고). html 목록은 None을 넘겨 fetch_html 기본값을 그대로 쓴다.
XML_LISTING_CONTENT_TYPES = (
    "application/xml",
    "text/xml",
    "application/rss+xml",
    "application/atom+xml",
)
LISTING_CONTENT_TYPES_BY_SOURCE_TYPE = {
    DraftSource.SourceType.RSS: XML_LISTING_CONTENT_TYPES,
    DraftSource.SourceType.SITEMAP: XML_LISTING_CONTENT_TYPES,
    DraftSource.SourceType.HTML: None,
}


@dataclass(frozen=True)
class CandidateOutcome:
    created: bool = False
    held_back: bool = False
    errored: bool = False
    consumed_fetch_budget: bool = False
    skip_key: str = None


def decide_and_create_candidate(
    source,
    url,
    *,
    already_exists,
    budget_available,
    at_creation_cap,
    robots_checker,
    stderr,
    create_draft,
):
    if already_exists:
        return CandidateOutcome(skip_key="duplicate")
    if at_creation_cap or not budget_available:
        return CandidateOutcome(held_back=True)

    candidate_result = robots_checker.check(url)
    if not candidate_result.allowed:
        skip_key = ROBOTS_REASON_TO_SKIP_KEY[candidate_result.reason]
        return CandidateOutcome(consumed_fetch_budget=True, skip_key=skip_key)

    try:
        create_draft(source_url=url, source_name=source.name)
    except DraftCreationDuplicateError:
        return CandidateOutcome(consumed_fetch_budget=True, skip_key="duplicate")
    except DraftCreationEmptyExtractionError:
        return CandidateOutcome(consumed_fetch_budget=True, skip_key="empty")
    except Exception as exc:
        # URL과 예외 클래스 이름만 남긴다 — str(exc)는 응답 본문 등 가져온 내용을
        # 그대로 노출할 수 있어 쓰지 않는다.
        # except-ok: 예외 클래스 이름만 stderr에 남긴다
        stderr.write(f"후보 생성 실패 {url}: {type(exc).__name__}")
        return CandidateOutcome(consumed_fetch_budget=True, errored=True)

    return CandidateOutcome(consumed_fetch_budget=True, created=True)
