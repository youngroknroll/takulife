import datetime

import pytest
import httpx
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from drafts.fetching import MAX_RESPONSE_BYTES, ResponseTooLargeError, fetch_html
from drafts.models import EventDraft
from drafts.services import (
    DraftCreationEmptyExtractionError,
    DraftCreationDuplicateError,
    DraftCreationUnsafeUrlError,
    DraftImmutableFieldError,
    DraftPublicationError,
    DraftStateError,
    approve_draft,
    create_draft_from_fields,
    create_draft_from_url,
    reject_draft,
    update_draft,
)
from drafts.url_safety import UnsafeFetchUrlError, validate_fetch_url
from events.models import Event


@pytest.mark.django_db
def test_approve_draft_creates_published_event_and_marks_draft_approved(make_user):
    actor = make_user()
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        source_name="Official",
        extracted_title="Popup event",
        extracted_category="popup_store",
        extracted_region="seoul",
    )

    before = timezone.now()
    result = approve_draft(draft.id, actor=actor)

    draft.refresh_from_db()
    event = Event.objects.get(id=result.event_id)
    assert result.draft.id == draft.id
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.official_url == "https://example.com/event"
    assert event.title == "Popup event"
    assert event.category == "popup_store"
    assert draft.reviewed_by_id == actor.id
    assert draft.approved_at is not None
    assert draft.approved_at >= before


@pytest.mark.django_db
def test_reject_draft_marks_draft_rejected_without_creating_event(make_user):
    actor = make_user()
    draft = EventDraft.objects.create(
        source_url="https://example.com/rejected-event",
        extracted_title="Rejected event",
    )

    before = timezone.now()
    result = reject_draft(draft.id, actor=actor)

    draft.refresh_from_db()
    assert result.id == draft.id
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert not Event.objects.filter(official_url="https://example.com/rejected-event").exists()
    assert draft.reviewed_by_id == actor.id
    assert draft.rejected_at is not None
    assert draft.rejected_at >= before
    assert draft.rejection_reason == ""


@pytest.mark.django_db
def test_reject_draft_records_rejection_reason(make_user):
    actor = make_user()
    draft = EventDraft.objects.create(source_url="https://example.com/rejected-with-reason")

    reject_draft(draft.id, actor=actor, rejection_reason="duplicate listing")

    draft.refresh_from_db()
    assert draft.rejection_reason == "duplicate listing"


@pytest.mark.django_db
def test_approve_draft_attribution_survives_approve_then_publish(make_user):
    actor = make_user()
    draft = EventDraft.objects.create(
        source_url="https://example.com/attributed-event",
        extracted_title="Attributed event",
    )

    result = approve_draft(draft.id, actor=actor)

    draft.refresh_from_db()
    assert Event.objects.filter(id=result.event_id, publish_status=Event.PublishStatus.PUBLISHED).exists()
    assert draft.reviewed_by_id == actor.id
    assert draft.approved_at is not None


@pytest.mark.django_db
def test_approve_draft_with_inverted_period_raises_and_stays_pending(make_user):
    actor = make_user()
    draft = EventDraft.objects.create(
        source_url="https://example.com/inverted-period",
        extracted_title="Inverted period event",
        extracted_start_date=datetime.date(2026, 8, 10),
        extracted_end_date=datetime.date(2026, 8, 1),
    )

    with pytest.raises(DraftPublicationError):
        approve_draft(draft.id, actor=actor)

    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert not Event.objects.filter(official_url="https://example.com/inverted-period").exists()


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


@pytest.mark.django_db
def test_create_draft_from_url_rejects_unsafe_redirect_target(monkeypatch):
    client_class = httpx.Client

    def handler(request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    monkeypatch.setattr(
        "drafts.fetching.httpx.Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(
        "drafts.fetching.validate_fetch_url",
        lambda url, **kwargs: validate_fetch_url(url),
    )

    with pytest.raises(DraftCreationUnsafeUrlError):
        create_draft_from_url("https://example.com/event")


def test_validate_fetch_url_rejects_hostname_resolving_to_loopback():
    def resolve_loopback(_hostname, _port, type):
        return [(2, type, 6, "", ("127.0.0.1", 0))]

    with pytest.raises(UnsafeFetchUrlError):
        validate_fetch_url("https://public.example/event", resolver=resolve_loopback)


def test_create_draft_from_url_rejects_oversized_response_before_full_read(monkeypatch):
    chunks_read = 0
    client_class = httpx.Client

    def handler(request):
        class CountingStream(httpx.SyncByteStream):
            def __iter__(self):
                nonlocal chunks_read
                for chunk in (b"a" * MAX_RESPONSE_BYTES, b"bc", b"unread"):
                    chunks_read += 1
                    yield chunk

        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            stream=CountingStream(),
        )

    monkeypatch.setattr(
        "drafts.fetching.httpx.Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr("drafts.fetching.validate_fetch_url", lambda url, **kwargs: None)

    with pytest.raises(ResponseTooLargeError):
        fetch_html("https://example.com/event")

    assert chunks_read == 2


@pytest.mark.django_db
def test_create_draft_from_url_maps_duplicate_create_race(monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<title>Event</title>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Event", "raw_text": "Summary"},
    )

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("drafts.services.EventDraft.objects.create", raise_integrity_error)

    with pytest.raises(DraftCreationDuplicateError):
        create_draft_from_url("https://example.com/event")


@pytest.mark.django_db
def test_create_draft_from_url_wraps_duplicate_create_in_savepoint(monkeypatch):
    """The EventDraft.objects.create() call must run inside its own nested
    atomic block (a savepoint), so that when it is invoked from within an
    outer transaction.atomic() (e.g. core.promotion.promote_personal_entry),
    an IntegrityError caught here does not leave the surrounding transaction
    unusable for the caller's subsequent queries (Postgres aborts the whole
    transaction on a statement error unless it ran under a savepoint)."""
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<title>Event</title>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Event", "raw_text": "Summary"},
    )

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("drafts.services.EventDraft.objects.create", raise_integrity_error)

    with transaction.atomic():
        with CaptureQueriesContext(connection) as ctx:
            with pytest.raises(DraftCreationDuplicateError):
                create_draft_from_url("https://example.com/event")

    assert any("SAVEPOINT" in query["sql"].upper() for query in ctx.captured_queries)


@pytest.mark.django_db
def test_create_draft_from_fields_wraps_duplicate_create_in_savepoint(monkeypatch):
    """Same savepoint guarantee as create_draft_from_url, for the direct
    (no-fetch) creation path used by core.promotion.promote_personal_entry,
    which calls this function from inside its own outer transaction.atomic()."""

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("drafts.services.EventDraft.objects.create", raise_integrity_error)

    with transaction.atomic():
        with CaptureQueriesContext(connection) as ctx:
            with pytest.raises(DraftCreationDuplicateError):
                create_draft_from_fields(source_url="https://example.com/manual", title="A")

    assert any("SAVEPOINT" in query["sql"].upper() for query in ctx.captured_queries)


@pytest.mark.django_db
def test_update_draft_rejects_immutable_fields_even_without_serializer():
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    with pytest.raises(DraftImmutableFieldError):
        update_draft(draft.id, {"review_status": EventDraft.ReviewStatus.APPROVED})
