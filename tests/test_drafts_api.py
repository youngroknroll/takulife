import pytest
from django.urls import reverse

from drafts.models import EventDraft
from events.models import Event


def event_drafts_url():
    return reverse("event-drafts")


def event_draft_detail_url(draft_id):
    return reverse("event-draft-detail", kwargs={"pk": draft_id})


def event_draft_approve_url(draft_id):
    return reverse("event-draft-approve", kwargs={"pk": draft_id})


def event_draft_reject_url(draft_id):
    return reverse("event-draft-reject", kwargs={"pk": draft_id})


@pytest.mark.django_db
def test_admin_can_create_event_draft_from_url(admin_client, monkeypatch):
    def fake_fetch(url):
        return "<html><title>Sample Event</title><meta name='description' content='Short summary'></html>"

    def fake_extract(html):
        return {
            "raw_title": "Sample Event",
            "raw_text": "Short summary",
            "extracted_title": "Sample Event",
            "extracted_summary": "Short summary",
            "extracted_category": "popup_store",
            "extracted_region": "seoul",
        }

    monkeypatch.setattr("drafts.services.fetch_html", fake_fetch)
    monkeypatch.setattr("drafts.services.extract_event_fields", fake_extract)
    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 201
    created = EventDraft.objects.get(source_url="https://example.com/event")
    assert created.extracted_title == "Sample Event"
    assert created.extracted_category == "popup_store"
    assert created.review_status == EventDraft.ReviewStatus.PENDING


@pytest.mark.django_db
def test_admin_create_event_draft_rejects_unsafe_url(admin_client):
    response = admin_client.post(event_drafts_url(), {"source_url": "http://127.0.0.1/event"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsafe URL is not allowed."}
    assert not EventDraft.objects.filter(source_url="http://127.0.0.1/event").exists()


@pytest.mark.django_db
def test_admin_create_event_draft_maps_fetch_error_to_503(admin_client, monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: (_ for _ in ()).throw(RuntimeError("timeout")))
    admin_client.raise_request_exception = False

    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Failed to fetch source URL."}
    assert not EventDraft.objects.filter(source_url="https://example.com/event").exists()


@pytest.mark.django_db
def test_admin_can_retrieve_event_draft(admin_client):
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.get(event_draft_detail_url(draft.id))

    assert response.status_code == 200
    assert response.json()["id"] == draft.id


@pytest.mark.django_db
def test_admin_can_patch_pending_event_draft(admin_client):
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Updated title", "extracted_region": "seoul"},
        content_type="application/json",
    )

    assert response.status_code == 200
    draft.refresh_from_db()
    assert draft.extracted_title == "Updated title"
    assert draft.extracted_region == "seoul"


@pytest.mark.django_db
def test_admin_cannot_patch_approved_event_draft(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        extracted_title="Original title",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.extracted_title == "Original title"


@pytest.mark.django_db
def test_admin_cannot_patch_rejected_event_draft(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        extracted_title="Original title",
        review_status=EventDraft.ReviewStatus.REJECTED,
    )

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.extracted_title == "Original title"


@pytest.mark.django_db
def test_admin_cannot_patch_source_url_or_raw_fields(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        raw_title="Original raw title",
        raw_text="Original raw text",
    )

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {
            "source_url": "https://example.com/changed",
            "raw_title": "Changed raw title",
            "raw_text": "Changed raw text",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    response_data = response.json()
    assert "source_url" in response_data
    assert "raw_title" in response_data
    assert "raw_text" in response_data
    draft.refresh_from_db()
    assert draft.source_url == "https://example.com/event"
    assert draft.raw_title == "Original raw title"
    assert draft.raw_text == "Original raw text"


@pytest.mark.django_db
def test_admin_cannot_patch_review_status(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        extracted_title="Original title",
    )

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {
            "review_status": EventDraft.ReviewStatus.APPROVED,
            "extracted_title": "Changed title",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"review_status": ["This field cannot be updated."]}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.extracted_title == "Original title"
    assert not Event.objects.filter(official_url="https://example.com/event").exists()


@pytest.mark.django_db
def test_admin_cannot_put_event_draft(admin_client):
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.put(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_admin_can_approve_event_draft(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        source_name="Official",
        extracted_title="Popup event",
        extracted_category="popup_store",
        extracted_work_title="Oshi Work",
        extracted_location_name="Seoul Mall",
        extracted_region="seoul",
        extracted_start_date="2026-06-01",
        extracted_end_date="2026-06-10",
        extracted_summary="Limited popup",
    )

    response = admin_client.post(event_draft_approve_url(draft.id))

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == draft.id
    assert response_data["source_url"] == "https://example.com/event"
    assert response_data["source_name"] == "Official"
    assert response_data["extracted_title"] == "Popup event"
    assert response_data["extracted_category"] == "popup_store"
    assert response_data["extracted_work_title"] == "Oshi Work"
    assert response_data["extracted_location_name"] == "Seoul Mall"
    assert response_data["extracted_region"] == "seoul"
    assert response_data["extracted_start_date"] == "2026-06-01"
    assert response_data["extracted_end_date"] == "2026-06-10"
    assert response_data["extracted_summary"] == "Limited popup"
    assert response_data["review_status"] == EventDraft.ReviewStatus.APPROVED
    assert "event_id" in response_data
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    event = Event.objects.get(official_url="https://example.com/event")
    assert response_data["event_id"] == event.id
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.title == "Popup event"
    assert event.category == "popup_store"


@pytest.mark.django_db
def test_admin_can_reject_event_draft(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/rejected-event",
        extracted_title="Rejected event",
    )

    response = admin_client.post(event_draft_reject_url(draft.id))

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == draft.id
    assert response_data["source_url"] == "https://example.com/rejected-event"
    assert response_data["extracted_title"] == "Rejected event"
    assert response_data["review_status"] == EventDraft.ReviewStatus.REJECTED
    assert "event_id" not in response_data
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert not Event.objects.filter(official_url="https://example.com/rejected-event").exists()


@pytest.mark.django_db
def test_non_admin_cannot_access_event_draft_review(client, django_user_model):
    user = django_user_model.objects.create_user(username="normal-user", password="secret")
    draft = EventDraft.objects.create(source_url="https://example.com/event")
    client.force_login(user)

    list_response = client.get(event_drafts_url())
    create_response = client.post(event_drafts_url(), {"source_url": "https://example.com/other"})
    detail_response = client.get(event_draft_detail_url(draft.id))
    patch_response = client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )
    approve_response = client.post(event_draft_approve_url(draft.id))
    reject_response = client.post(event_draft_reject_url(draft.id))

    assert list_response.status_code == 403
    assert create_response.status_code == 403
    assert detail_response.status_code == 403
    assert patch_response.status_code == 403
    assert approve_response.status_code == 403
    assert reject_response.status_code == 403


@pytest.mark.django_db
def test_duplicate_source_url_is_rejected_on_create(admin_client):
    EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 400
    assert "source_url" in response.json()


@pytest.mark.django_db
def test_non_http_source_url_is_rejected_on_create(admin_client):
    response = admin_client.post(event_drafts_url(), {"source_url": "ftp://example.com/event"})

    assert response.status_code == 400
    assert "source_url" in response.json()


@pytest.mark.django_db
def test_approve_rejects_duplicate_official_url(admin_client):
    Event.objects.create(
        title="Already published",
        official_url="https://example.com/event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        extracted_title="Duplicate event",
    )

    response = admin_client.post(event_draft_approve_url(draft.id))

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert Event.objects.filter(official_url="https://example.com/event").count() == 1


@pytest.mark.django_db
def test_approve_rejects_missing_official_url(admin_client):
    draft = EventDraft.objects.create(
        source_url="",
        extracted_title="No URL event",
    )

    response = admin_client.post(event_draft_approve_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"official_url": ["Official URL is required for publication."]}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING


@pytest.mark.django_db
def test_approved_event_draft_cannot_be_rejected(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    response = admin_client.post(event_draft_reject_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"detail": "Only pending drafts can be rejected."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED


@pytest.mark.django_db
def test_rejected_event_draft_cannot_be_approved(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.REJECTED,
    )

    response = admin_client.post(event_draft_approve_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"detail": "Only pending drafts can be approved."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED


@pytest.mark.django_db
def test_approved_event_draft_cannot_be_approved_again(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    response = admin_client.post(event_draft_approve_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"detail": "Only pending drafts can be approved."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED


@pytest.mark.django_db
def test_rejected_event_draft_cannot_be_rejected_again(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.REJECTED,
    )

    response = admin_client.post(event_draft_reject_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"detail": "Only pending drafts can be rejected."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED


@pytest.mark.django_db
def test_missing_event_draft_cannot_be_approved(admin_client):
    response = admin_client.post(event_draft_approve_url(999))

    assert response.status_code == 404


@pytest.mark.django_db
def test_missing_event_draft_cannot_be_rejected(admin_client):
    response = admin_client.post(event_draft_reject_url(999))

    assert response.status_code == 404


@pytest.mark.django_db
def test_approve_returns_controlled_error_when_event_creation_fails(admin_client, monkeypatch):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        extracted_title="Broken event",
    )

    def fail_create(*args, **kwargs):
        raise ValueError("event create failed")

    monkeypatch.setattr(Event.objects, "create", fail_create)
    admin_client.raise_request_exception = False

    response = admin_client.post(event_draft_approve_url(draft.id))

    assert response.status_code == 503
    assert response.json() == {"detail": "Event publication failed."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING


@pytest.mark.django_db
def test_admin_event_draft_legacy_route_is_not_supported(admin_client):
    response = admin_client.get("/api/admin/event-drafts/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_cannot_delete_event_draft(admin_client):
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.delete(event_draft_detail_url(draft.id))

    assert response.status_code == 405
    assert EventDraft.objects.filter(id=draft.id).exists()
