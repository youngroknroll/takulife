import pytest

from drafts.models import EventDraft
from drafts.services import approve_draft, reject_draft
from events.models import Event


@pytest.mark.django_db
def test_approve_draft_creates_published_event_and_marks_draft_approved():
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        source_name="Official",
        extracted_title="Popup event",
        extracted_category="popup_store",
        extracted_region="seoul",
    )

    result = approve_draft(draft.id)

    draft.refresh_from_db()
    event = Event.objects.get(id=result.event_id)
    assert result.draft.id == draft.id
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.official_url == "https://example.com/event"
    assert event.title == "Popup event"
    assert event.category == "popup_store"


@pytest.mark.django_db
def test_reject_draft_marks_draft_rejected_without_creating_event():
    draft = EventDraft.objects.create(
        source_url="https://example.com/rejected-event",
        extracted_title="Rejected event",
    )

    result = reject_draft(draft.id)

    draft.refresh_from_db()
    assert result.id == draft.id
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert not Event.objects.filter(official_url="https://example.com/rejected-event").exists()
