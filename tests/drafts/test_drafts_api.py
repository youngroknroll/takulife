import pytest
from django.db import IntegrityError
from django.urls import resolve, reverse

import drafts.views as draft_views
from drafts.models import EventDraft
from drafts.services import (
    DraftCreationEmptyExtractionError,
    DraftCreationResponseTooLargeError,
    DraftCreationUnsupportedContentError,
)
from events.models import Event


def _raise(exc):
    def _fn(*args, **kwargs):
        raise exc

    return _fn


def event_drafts_url():
    return reverse("event-drafts")


def event_draft_detail_url(draft_id):
    return reverse("event-draft-detail", kwargs={"pk": draft_id})


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
def test_admin_can_retrieve_event_draft(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.get(event_draft_detail_url(draft.id))

    assert response.status_code == 200
    assert response.json()["id"] == draft.id


@pytest.mark.django_db
def test_admin_retrieve_event_draft_includes_extraction_method_and_confidence(admin_client, make_draft):
    draft = make_draft("https://example.com/event", extraction_method=EventDraft.ExtractionMethod.LLM, confidence=0.87)

    response = admin_client.get(event_draft_detail_url(draft.id))

    response_data = response.json()
    assert response_data["extraction_method"] == "llm"
    assert response_data["confidence"] == pytest.approx(0.87)


@pytest.mark.django_db
def test_admin_can_patch_pending_event_draft(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

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
def test_admin_cannot_patch_approved_event_draft(admin_client, make_draft):
    draft = make_draft("https://example.com/event", extracted_title="Original title", review_status=EventDraft.ReviewStatus.APPROVED)

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.extracted_title == "Original title"


@pytest.mark.django_db
def test_admin_cannot_patch_rejected_event_draft(admin_client, make_draft):
    draft = make_draft("https://example.com/event", extracted_title="Original title", review_status=EventDraft.ReviewStatus.REJECTED)

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.extracted_title == "Original title"


@pytest.mark.django_db
def test_admin_cannot_patch_source_url_or_raw_fields(admin_client, make_draft):
    draft = make_draft("https://example.com/event", raw_title="Original raw title", raw_text="Original raw text")

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
def test_admin_cannot_patch_review_status(admin_client, make_draft):
    draft = make_draft("https://example.com/event", extracted_title="Original title")

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
def test_admin_cannot_patch_extraction_method_or_confidence(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extraction_method": "llm", "confidence": 0.9},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "extraction_method": ["This field cannot be updated."],
        "confidence": ["This field cannot be updated."],
    }
    draft.refresh_from_db()
    assert draft.extraction_method == EventDraft.ExtractionMethod.HEURISTIC
    assert draft.confidence is None


@pytest.mark.django_db
def test_admin_cannot_put_event_draft(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.put(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_non_admin_cannot_access_event_draft_review(client, make_user, make_draft):
    user = make_user()
    draft = make_draft("https://example.com/event")
    client.force_login(user)

    list_response = client.get(event_drafts_url())
    create_response = client.post(event_drafts_url(), {"source_url": "https://example.com/other"})
    detail_response = client.get(event_draft_detail_url(draft.id))
    patch_response = client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert list_response.status_code == 403
    assert create_response.status_code == 403
    assert detail_response.status_code == 403
    assert patch_response.status_code == 403


@pytest.mark.django_db
def test_duplicate_source_url_is_rejected_on_create(admin_client, make_draft):
    make_draft("https://example.com/event")

    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 400
    assert "source_url" in response.json()


@pytest.mark.django_db
def test_duplicate_source_url_race_uses_existing_field_error_contract(admin_client, monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<title>Event</title>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Event", "raw_text": "Summary"},
    )

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("drafts.services.EventDraft.objects.create", raise_integrity_error)

    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 400
    assert response.json() == {"source_url": ["Event draft with this source URL already exists."]}


@pytest.mark.django_db
def test_non_http_source_url_is_rejected_on_create(admin_client):
    response = admin_client.post(event_drafts_url(), {"source_url": "ftp://example.com/event"})

    assert response.status_code == 400
    assert "source_url" in response.json()


@pytest.mark.django_db
def test_admin_event_draft_legacy_route_is_not_supported(admin_client):
    response = admin_client.get("/api/admin/event-drafts/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_cannot_delete_event_draft(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.delete(event_draft_detail_url(draft.id))

    assert response.status_code == 405
    assert EventDraft.objects.filter(id=draft.id).exists()


# ---------------------------------------------------------------------------
# GET /api/event-drafts/stats/ (moved from tests/drafts/test_drafts_stats.py)
# ---------------------------------------------------------------------------


def stats_url():
    return reverse("event-draft-stats")


@pytest.mark.django_db
def test_admin_can_get_draft_stats_with_correct_counts(admin_client, make_draft):
    make_draft("https://example.com/p1")
    make_draft("https://example.com/p2")
    make_draft("https://example.com/a1", review_status=EventDraft.ReviewStatus.APPROVED)
    make_draft("https://example.com/r1", review_status=EventDraft.ReviewStatus.REJECTED)

    response = admin_client.get(stats_url())

    assert response.status_code == 200
    data = response.json()
    assert data["pending"] == 2
    assert data["approved"] == 1
    assert data["rejected"] == 1


@pytest.mark.django_db
def test_admin_gets_stats_with_all_zero_when_no_drafts(admin_client):
    response = admin_client.get(stats_url())

    assert response.status_code == 200
    data = response.json()
    assert data == {"pending": 0, "approved": 0, "rejected": 0}


@pytest.mark.django_db
def test_non_staff_user_cannot_get_draft_stats(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(stats_url())

    assert response.status_code == 403


@pytest.mark.django_db
def test_anonymous_user_cannot_get_draft_stats(client):
    response = client.get(stats_url())

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Route ordering: stats/ vs <int:pk>/ (moved from tests/drafts/test_drafts_stats.py)
# ---------------------------------------------------------------------------


class TestRouteOrdering:
    def test_stats_path_resolves_to_stats_view(self):
        match = resolve("/api/event-drafts/stats/")
        assert match.url_name == "event-draft-stats"

    def test_numeric_pk_path_resolves_to_detail_view(self):
        match = resolve("/api/event-drafts/1/")
        assert match.url_name == "event-draft-detail"


# ---------------------------------------------------------------------------
# POST /api/event-drafts/ error-mapping HTTP responses
# (moved from tests/drafts/test_draft_service_errors.py — same endpoint's home;
# the service-layer mapping tests stay there as TestCreateDraftErrorMapping.)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminCreateEndpointErrorResponses:
    def _post(self, client):
        return client.post(
            "/api/event-drafts/",
            data={"source_url": "https://ok.example.com/"},
            content_type="application/json",
        )

    def test_unsupported_content_returns_400(self, staff_client, monkeypatch):
        monkeypatch.setattr(
            draft_views, "create_draft_from_url",
            _raise(DraftCreationUnsupportedContentError()),
        )
        _, client = staff_client(is_superuser=True)
        resp = self._post(client)
        assert resp.status_code == 400

    def test_response_too_large_returns_400(self, staff_client, monkeypatch):
        monkeypatch.setattr(
            draft_views, "create_draft_from_url",
            _raise(DraftCreationResponseTooLargeError()),
        )
        _, client = staff_client(is_superuser=True)
        resp = self._post(client)
        assert resp.status_code == 400

    def test_empty_extraction_returns_400(self, staff_client, monkeypatch):
        monkeypatch.setattr(
            draft_views, "create_draft_from_url",
            _raise(DraftCreationEmptyExtractionError()),
        )
        _, client = staff_client(is_superuser=True)
        resp = self._post(client)
        assert resp.status_code == 400
