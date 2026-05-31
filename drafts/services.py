from dataclasses import dataclass

from django.db import transaction

from events.services import (
    DuplicateOfficialUrlError,
    MissingOfficialUrlError,
    PublishEventError,
    create_published_event,
)

from .extraction import EmptyExtractionError, extract_event_fields
from .fetching import FetchError, ResponseTooLargeError, UnsupportedContentTypeError, fetch_html
from .models import EventDraft
from .url_safety import InvalidFetchUrlError, UnsafeFetchUrlError, validate_fetch_url


class DraftStateError(Exception):
    pass


class DraftNotFoundError(Exception):
    pass


class DraftPublicationDuplicateError(Exception):
    pass


class DraftPublicationMissingOfficialUrlError(Exception):
    pass


class DraftPublicationError(Exception):
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


@dataclass(frozen=True)
class DraftApprovalResult:
    draft: EventDraft
    event_id: int


def create_draft_from_url(source_url, source_name=""):
    try:
        validate_fetch_url(source_url)
    except InvalidFetchUrlError as exc:
        raise ValueError("invalid source url") from exc
    except UnsafeFetchUrlError as exc:
        raise DraftCreationUnsafeUrlError from exc

    try:
        html = fetch_html(source_url)
    except UnsupportedContentTypeError as exc:
        raise DraftCreationUnsupportedContentError from exc
    except ResponseTooLargeError as exc:
        raise DraftCreationResponseTooLargeError from exc
    except FetchError as exc:
        raise DraftCreationFetchError from exc
    except Exception as exc:
        raise DraftCreationFetchError from exc

    try:
        extracted = extract_event_fields(html)
    except EmptyExtractionError as exc:
        raise DraftCreationEmptyExtractionError from exc

    if not extracted.get("raw_title") and not extracted.get("raw_text"):
        raise DraftCreationEmptyExtractionError

    return EventDraft.objects.create(
        source_url=source_url,
        source_name=source_name,
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
        review_status=EventDraft.ReviewStatus.PENDING,
    )


def update_draft(draft_id, updates):
    with transaction.atomic():
        try:
            draft = EventDraft.objects.select_for_update().get(pk=draft_id)
        except EventDraft.DoesNotExist as exc:
            raise DraftNotFoundError from exc

        if draft.review_status != EventDraft.ReviewStatus.PENDING:
            raise DraftStateError

        for field, value in updates.items():
            setattr(draft, field, value)

        update_fields = list(updates.keys()) + ["updated_at"]
        draft.save(update_fields=update_fields)
        return draft


def approve_draft(draft_id):
    with transaction.atomic():
        try:
            draft = EventDraft.objects.select_for_update().get(pk=draft_id)
        except EventDraft.DoesNotExist as exc:
            raise DraftNotFoundError from exc

        if draft.review_status != EventDraft.ReviewStatus.PENDING:
            raise DraftStateError

        try:
            event = create_published_event(
                title=draft.extracted_title or draft.raw_title or draft.source_url,
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
        except PublishEventError as exc:
            raise DraftPublicationError from exc

        draft.review_status = EventDraft.ReviewStatus.APPROVED
        draft.save(update_fields=["review_status", "updated_at"])
        return DraftApprovalResult(draft=draft, event_id=event.id)


def reject_draft(draft_id):
    with transaction.atomic():
        try:
            draft = EventDraft.objects.select_for_update().get(pk=draft_id)
        except EventDraft.DoesNotExist as exc:
            raise DraftNotFoundError from exc

        if draft.review_status != EventDraft.ReviewStatus.PENDING:
            raise DraftStateError

        draft.review_status = EventDraft.ReviewStatus.REJECTED
        draft.save(update_fields=["review_status", "updated_at"])
        return draft
