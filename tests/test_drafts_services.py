import pytest

from drafts.models import EventDraft
from drafts.services import (
    DraftCreationEmptyExtractionError,
    DraftStateError,
    approve_draft,
    create_draft_from_url,
    reject_draft,
    update_draft,
)
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


@pytest.mark.django_db
def test_update_draft_updates_pending_draft_fields():
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    updated = update_draft(draft.id, {"extracted_title": "Updated title", "extracted_region": "seoul"})

    draft.refresh_from_db()
    assert updated.id == draft.id
    assert draft.extracted_title == "Updated title"
    assert draft.extracted_region == "seoul"


@pytest.mark.django_db
def test_update_draft_rejects_non_pending_state():
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    with pytest.raises(DraftStateError):
        update_draft(draft.id, {"extracted_title": "Updated title"})


@pytest.mark.django_db
def test_create_draft_from_url_fetches_and_extracts(monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Sample Event</title></html>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {
            "raw_title": "Sample Event",
            "raw_text": "Sample summary",
            "extracted_title": "Sample Event",
            "extracted_summary": "Sample summary",
            "extracted_category": "popup_store",
            "extracted_region": "seoul",
        },
    )

    draft = create_draft_from_url("https://example.com/event")

    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.raw_title == "Sample Event"
    assert draft.extracted_title == "Sample Event"
    assert draft.extracted_category == "popup_store"


@pytest.mark.django_db
def test_create_draft_from_url_raises_when_extraction_empty(monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html></html>")
    monkeypatch.setattr("drafts.services.extract_event_fields", lambda html: {"raw_title": "", "raw_text": ""})

    with pytest.raises(DraftCreationEmptyExtractionError):
        create_draft_from_url("https://example.com/event")
