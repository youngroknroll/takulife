import pytest

from drafts.models import EventDraft
from events.models import Event


@pytest.mark.django_db
def test_admin_can_create_event_draft_from_url(admin_client):
    response = admin_client.post("/api/admin/event-drafts/", {"source_url": "https://example.com/event"})

    assert response.status_code == 201


@pytest.mark.django_db
def test_admin_can_retrieve_event_draft(admin_client):
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.get(f"/api/admin/event-drafts/{draft.id}/")

    assert response.status_code == 200
    assert response.json()["id"] == draft.id


@pytest.mark.django_db
def test_admin_can_patch_pending_event_draft(admin_client):
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.patch(
        f"/api/admin/event-drafts/{draft.id}/",
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
        f"/api/admin/event-drafts/{draft.id}/",
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
        f"/api/admin/event-drafts/{draft.id}/",
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
        f"/api/admin/event-drafts/{draft.id}/",
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
def test_admin_cannot_put_event_draft(admin_client):
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.put(
        f"/api/admin/event-drafts/{draft.id}/",
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

    response = admin_client.post(f"/api/admin/event-drafts/{draft.id}/approve/")

    assert response.status_code == 200
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    event = Event.objects.get(official_url="https://example.com/event")
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.title == "Popup event"
    assert event.category == "popup_store"


@pytest.mark.django_db
def test_admin_can_reject_event_draft(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/rejected-event",
        extracted_title="Rejected event",
    )

    response = admin_client.post(f"/api/admin/event-drafts/{draft.id}/reject/")

    assert response.status_code == 200
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert not Event.objects.filter(official_url="https://example.com/rejected-event").exists()


@pytest.mark.django_db
def test_non_admin_cannot_access_event_draft_review(client, django_user_model):
    user = django_user_model.objects.create_user(username="normal-user", password="secret")
    draft = EventDraft.objects.create(source_url="https://example.com/event")
    client.force_login(user)

    list_response = client.get("/api/admin/event-drafts/")
    create_response = client.post("/api/admin/event-drafts/", {"source_url": "https://example.com/other"})
    detail_response = client.get(f"/api/admin/event-drafts/{draft.id}/")
    patch_response = client.patch(
        f"/api/admin/event-drafts/{draft.id}/",
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )
    approve_response = client.post(f"/api/admin/event-drafts/{draft.id}/approve/")
    reject_response = client.post(f"/api/admin/event-drafts/{draft.id}/reject/")

    assert list_response.status_code == 403
    assert create_response.status_code == 403
    assert detail_response.status_code == 403
    assert patch_response.status_code == 403
    assert approve_response.status_code == 403
    assert reject_response.status_code == 403


@pytest.mark.django_db
def test_duplicate_source_url_is_rejected_on_create(admin_client):
    EventDraft.objects.create(source_url="https://example.com/event")

    response = admin_client.post("/api/admin/event-drafts/", {"source_url": "https://example.com/event"})

    assert response.status_code == 400
    assert "source_url" in response.json()


@pytest.mark.django_db
def test_non_http_source_url_is_rejected_on_create(admin_client):
    response = admin_client.post("/api/admin/event-drafts/", {"source_url": "ftp://example.com/event"})

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

    response = admin_client.post(f"/api/admin/event-drafts/{draft.id}/approve/")

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert Event.objects.filter(official_url="https://example.com/event").count() == 1


@pytest.mark.django_db
def test_approved_event_draft_cannot_be_rejected(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    response = admin_client.post(f"/api/admin/event-drafts/{draft.id}/reject/")

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED


@pytest.mark.django_db
def test_rejected_event_draft_cannot_be_approved(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.REJECTED,
    )

    response = admin_client.post(f"/api/admin/event-drafts/{draft.id}/approve/")

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED


@pytest.mark.django_db
def test_approved_event_draft_cannot_be_approved_again(admin_client):
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    response = admin_client.post(f"/api/admin/event-drafts/{draft.id}/approve/")

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED


@pytest.mark.django_db
def test_missing_event_draft_cannot_be_approved(admin_client):
    response = admin_client.post("/api/admin/event-drafts/999/approve/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_missing_event_draft_cannot_be_rejected(admin_client):
    response = admin_client.post("/api/admin/event-drafts/999/reject/")

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

    response = admin_client.post(f"/api/admin/event-drafts/{draft.id}/approve/")

    assert response.status_code == 503
    assert response.json() == {"detail": "Event publication failed."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
