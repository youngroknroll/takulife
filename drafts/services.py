from dataclasses import dataclass

from django.db import transaction

from events.services import DuplicateOfficialUrlError, PublishEventError, create_published_event

from .models import EventDraft


class DraftStateError(Exception):
    pass


class DraftNotFoundError(Exception):
    pass


class DraftPublicationDuplicateError(Exception):
    pass


class DraftPublicationError(Exception):
    pass


@dataclass(frozen=True)
class DraftApprovalResult:
    draft: EventDraft
    event_id: int


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
