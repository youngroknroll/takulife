import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.vocab import is_valid_category, is_valid_region
from events.services import (
    DuplicateOfficialUrlError,
    MissingOfficialUrlError,
    PublishEventError,
    PublishEventTitleError,
    create_published_event,
)

from .extraction import EmptyExtractionError, extract_event_fields, parse_raw_fields
from .fetching import ResponseTooLargeError, UnsupportedContentTypeError, fetch_html
from .llm_extraction import extract_event_fields_llm
from .models import EventDraft
from .url_safety import InvalidFetchUrlError, UnsafeFetchUrlError, validate_fetch_url

logger = logging.getLogger(__name__)


class DraftStateError(Exception):
    pass


class DraftImmutableFieldError(Exception):
    pass


class DraftVocabError(Exception):
    """드래프트 수정에서 extracted_category/extracted_region을 core.vocab에 없는
    값으로 바꾸려 할 때 발생한다. 승인 시점이 아니라 수정 시점에 바로 막는다 —
    입력한 담당자가 즉시 알아야 하고, 잘못된 값이 정상처럼 보이며 검수 대기열에
    남아 있으면 안 된다."""

    pass


class DraftNotFoundError(Exception):
    pass


class DraftPublicationDuplicateError(Exception):
    pass


class DraftPublicationMissingOfficialUrlError(Exception):
    pass


class DraftPublicationError(Exception):
    pass


class DraftPublicationTitleError(Exception):
    pass


class DraftCreationUnsafeUrlError(Exception):
    pass


class DraftCreationFetchError(Exception):
    pass


class DraftCreationUnsupportedContentError(Exception):
    pass


class DraftCreationResponseTooLargeError(Exception):
    pass


class DraftCreationEmptyExtractionError(Exception):
    pass


class DraftCreationDuplicateError(Exception):
    pass


@dataclass(frozen=True)
class DraftApprovalResult:
    draft: EventDraft
    event_id: int


@dataclass(frozen=True)
class DraftPayload:
    source_url: str
    raw_title: str
    raw_text: str
    extracted_title: str
    extracted_category: str
    extracted_work_title: str
    extracted_location_name: str
    extracted_region: str
    extracted_start_date: object
    extracted_end_date: object
    extracted_summary: str
    confidence: object
    extraction_method: str


def prepare_draft_from_url(*, source_url):
    """원본 URL을 가져와 필드를 추출한다. DB 접근이 없다 — fetch_html의
    타임아웃(최대 4홉)이 DB 트랜잭션 안에 들어가지 않게 하기 위해서다."""
    try:
        validate_fetch_url(source_url)
    except InvalidFetchUrlError as exc:
        raise ValueError("invalid source url") from exc
    except UnsafeFetchUrlError as exc:
        parsed = urlparse(source_url)
        logger.warning(
            "Rejected unsafe fetch URL: scheme=%s host=%r", parsed.scheme, parsed.hostname
        )
        raise DraftCreationUnsafeUrlError from exc

    try:
        html = fetch_html(source_url)
    except UnsafeFetchUrlError as exc:
        parsed = urlparse(source_url)
        logger.warning(
            "Rejected unsafe fetch URL during fetch: scheme=%s host=%r",
            parsed.scheme,
            parsed.hostname,
        )
        raise DraftCreationUnsafeUrlError from exc
    except UnsupportedContentTypeError as exc:
        raise DraftCreationUnsupportedContentError from exc
    except ResponseTooLargeError as exc:
        raise DraftCreationResponseTooLargeError from exc
    except Exception as exc:
        raise DraftCreationFetchError from exc

    if settings.DRAFT_LLM_EXTRACTION_ENABLED:
        try:
            raw_fields = parse_raw_fields(html)
        except EmptyExtractionError as exc:
            raise DraftCreationEmptyExtractionError from exc
        extracted = extract_event_fields_llm(raw_fields["raw_title"], raw_fields["raw_text"])
    else:
        try:
            extracted = extract_event_fields(html)
        except EmptyExtractionError as exc:
            raise DraftCreationEmptyExtractionError from exc

    if not extracted.get("raw_title") and not extracted.get("raw_text"):
        raise DraftCreationEmptyExtractionError

    return DraftPayload(
        source_url=source_url,
        raw_title=extracted.get("raw_title", ""),
        raw_text=extracted.get("raw_text", ""),
        extracted_title=extracted.get("extracted_title", ""),
        extracted_category=extracted.get("extracted_category", ""),
        extracted_work_title=extracted.get("extracted_work_title", ""),
        extracted_location_name=extracted.get("extracted_location_name", ""),
        extracted_region=extracted.get("extracted_region", ""),
        extracted_start_date=extracted.get("extracted_start_date"),
        extracted_end_date=extracted.get("extracted_end_date"),
        extracted_summary=extracted.get("extracted_summary", ""),
        confidence=extracted.get("confidence"),
        extraction_method=extracted.get(
            "extraction_method", EventDraft.ExtractionMethod.HEURISTIC
        ),
    )


def persist_prepared_draft(*, payload, source_name=""):
    """준비된 페이로드를 저장한다. 중복 source_url은 여기서만 DraftCreationDuplicateError로
    바뀐다 — prepare_draft_from_url은 DB를 보지 않으므로 중복을 낼 수 없다."""
    try:
        with transaction.atomic():
            return EventDraft.objects.create(
                source_url=payload.source_url,
                source_name=source_name,
                raw_title=payload.raw_title,
                raw_text=payload.raw_text,
                extracted_title=payload.extracted_title,
                extracted_category=payload.extracted_category,
                extracted_work_title=payload.extracted_work_title,
                extracted_location_name=payload.extracted_location_name,
                extracted_region=payload.extracted_region,
                extracted_start_date=payload.extracted_start_date,
                extracted_end_date=payload.extracted_end_date,
                extracted_summary=payload.extracted_summary,
                confidence=payload.confidence,
                extraction_method=payload.extraction_method,
                review_status=EventDraft.ReviewStatus.PENDING,
            )
    except IntegrityError as exc:
        raise DraftCreationDuplicateError from exc


def create_draft_from_url(*, source_url, source_name=""):
    payload = prepare_draft_from_url(source_url=source_url)
    return persist_prepared_draft(payload=payload, source_name=source_name)


def create_draft_from_fields(
    *,
    source_url,
    source_name="",
    title="",
    category="",
    work_title="",
    location_name="",
    region="",
    summary="",
):
    """fetch 없이 호출자가 준 필드로 바로 PENDING 드래프트를 만든다. 사용자가 비공식
    으로 등록한 항목을 공식 제보하는 등, 이미 가진 데이터로 검수 파이프라인에 넣을
    때 쓴다. source_url은 공식 URL이며 여기서 유일해야 하고, 승인되면 게시된
    이벤트의 official_url이 된다. 필드는 관리자가 검수·수정하는 것과 같은
    extracted_* 자리에 들어가므로 게시 전에 자유 텍스트 category/region을 고칠 수
    있다.
    """
    try:
        with transaction.atomic():
            return EventDraft.objects.create(
                source_url=source_url,
                source_name=source_name,
                extracted_title=title,
                extracted_category=category,
                extracted_work_title=work_title,
                extracted_location_name=location_name,
                extracted_region=region,
                extracted_summary=summary,
                review_status=EventDraft.ReviewStatus.PENDING,
            )
    except IntegrityError as exc:
        raise DraftCreationDuplicateError from exc


def _get_pending_draft_for_update(draft_id):
    try:
        draft = EventDraft.objects.select_for_update().get(pk=draft_id)
    except EventDraft.DoesNotExist as exc:
        raise DraftNotFoundError from exc

    if draft.review_status != EventDraft.ReviewStatus.PENDING:
        raise DraftStateError

    return draft


def _category_update_invalid(updates) -> bool:
    """updates에 extracted_category가 있는데 유효하지 않은 값이면 True."""
    return "extracted_category" in updates and not is_valid_category(
        updates["extracted_category"] or ""
    )


def _region_update_invalid(updates) -> bool:
    """updates에 extracted_region이 있는데 유효하지 않은 값이면 True."""
    return "extracted_region" in updates and not is_valid_region(
        updates["extracted_region"] or ""
    )


def update_draft(*, draft_id, updates):
    mutable_fields = {
        "source_name",
        "extracted_title",
        "extracted_category",
        "extracted_work_title",
        "extracted_location_name",
        "extracted_region",
        "extracted_start_date",
        "extracted_end_date",
        "extracted_summary",
    }
    if not set(updates).issubset(mutable_fields):
        raise DraftImmutableFieldError

    # 위에서는 어떤 필드를 바꿀 수 있는지 검사했고, 여기서는 그 값이 유효한지
    # 검사한다. 이게 없으면 수기로 고친 자유 텍스트가 검증 없이 approve_draft를
    # 거쳐 게시된 이벤트까지 들어간다. atomic 블록 전에 검사해야 거부된 값이
    # 아무것도 저장되지 않는다 — 부분 저장되면 화면과 DB가 어긋난다.
    if _category_update_invalid(updates):
        raise DraftVocabError
    if _region_update_invalid(updates):
        raise DraftVocabError

    with transaction.atomic():
        draft = _get_pending_draft_for_update(draft_id)

        for field, value in updates.items():
            setattr(draft, field, value)

        update_fields = list(updates.keys()) + ["updated_at"]
        draft.save(update_fields=update_fields)
        return draft


def approve_draft(*, draft_id, actor):
    with transaction.atomic():
        draft = _get_pending_draft_for_update(draft_id)

        try:
            event = create_published_event(
                title=draft.extracted_title or draft.raw_title,
                category=draft.extracted_category,
                work_title=draft.extracted_work_title,
                location_name=draft.extracted_location_name,
                region=draft.extracted_region,
                start_date=draft.extracted_start_date,
                end_date=draft.extracted_end_date,
                official_url=draft.source_url,
                source_name=draft.source_name,
                summary=draft.extracted_summary,
            )
        except DuplicateOfficialUrlError as exc:
            raise DraftPublicationDuplicateError from exc
        except MissingOfficialUrlError as exc:
            raise DraftPublicationMissingOfficialUrlError from exc
        except PublishEventTitleError as exc:
            raise DraftPublicationTitleError from exc
        except PublishEventError as exc:
            raise DraftPublicationError from exc

        draft.review_status = EventDraft.ReviewStatus.APPROVED
        draft.reviewed_by = actor
        draft.approved_at = timezone.now()
        draft.save(update_fields=["review_status", "reviewed_by", "approved_at", "updated_at"])
        return DraftApprovalResult(draft=draft, event_id=event.id)


def reject_draft(*, draft_id, actor, rejection_reason=""):
    with transaction.atomic():
        draft = _get_pending_draft_for_update(draft_id)
        draft.review_status = EventDraft.ReviewStatus.REJECTED
        draft.reviewed_by = actor
        draft.rejected_at = timezone.now()
        draft.rejection_reason = rejection_reason
        draft.save(
            update_fields=[
                "review_status",
                "reviewed_by",
                "rejected_at",
                "rejection_reason",
                "updated_at",
            ]
        )
        return draft
