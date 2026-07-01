"""Tests for Phase 3: draft stats endpoint and staff guard on HTML views.

Covers:
- draft_review_stats() unit test: correct counts, all keys present when some statuses absent
- GET /api/event-drafts/stats/ endpoint: admin 200 with correct counts, non-staff 403, anon 403
- Route ordering: stats/ resolves to stats view, not detail view; numeric pk resolves to detail
- Staff guard: anonymous GET /event-drafts/ and /event-drafts/<id>/ -> 302; staff GET -> 200
"""
import secrets

import pytest
from django.urls import reverse, resolve

from drafts.models import EventDraft


# Throwaway password generated at runtime for test users — kept out of source
# so secret scanners do not flag a hardcoded credential. Not a real secret.
TEST_PASSWORD = "Aa1!" + secrets.token_urlsafe(16)


# ---------------------------------------------------------------------------
# draft_review_stats() unit tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDraftReviewStats:
    def test_all_three_keys_present_when_no_drafts(self):
        from drafts.queries import draft_review_stats

        result = draft_review_stats()

        assert set(result.keys()) == {"pending", "approved", "rejected"}
        assert result["pending"] == 0
        assert result["approved"] == 0
        assert result["rejected"] == 0

    def test_counts_match_review_status_distribution(self):
        from drafts.queries import draft_review_stats

        EventDraft.objects.create(source_url="https://example.com/a")
        EventDraft.objects.create(source_url="https://example.com/b")
        EventDraft.objects.create(
            source_url="https://example.com/c",
            review_status=EventDraft.ReviewStatus.APPROVED,
        )
        EventDraft.objects.create(
            source_url="https://example.com/d",
            review_status=EventDraft.ReviewStatus.REJECTED,
        )

        result = draft_review_stats()

        assert result["pending"] == 2
        assert result["approved"] == 1
        assert result["rejected"] == 1

    def test_all_three_keys_present_when_only_pending_exist(self):
        from drafts.queries import draft_review_stats

        EventDraft.objects.create(source_url="https://example.com/only-pending")

        result = draft_review_stats()

        assert result["pending"] == 1
        assert result["approved"] == 0
        assert result["rejected"] == 0

    def test_all_keys_present_when_only_approved_exist(self):
        from drafts.queries import draft_review_stats

        EventDraft.objects.create(
            source_url="https://example.com/only-approved",
            review_status=EventDraft.ReviewStatus.APPROVED,
        )

        result = draft_review_stats()

        assert result["pending"] == 0
        assert result["approved"] == 1
        assert result["rejected"] == 0


# ---------------------------------------------------------------------------
# GET /api/event-drafts/stats/ endpoint
# ---------------------------------------------------------------------------

def stats_url():
    return reverse("event-draft-stats")


@pytest.mark.django_db
def test_admin_can_get_draft_stats_with_correct_counts(admin_client):
    EventDraft.objects.create(source_url="https://example.com/p1")
    EventDraft.objects.create(source_url="https://example.com/p2")
    EventDraft.objects.create(
        source_url="https://example.com/a1",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )
    EventDraft.objects.create(
        source_url="https://example.com/r1",
        review_status=EventDraft.ReviewStatus.REJECTED,
    )

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
def test_non_staff_user_cannot_get_draft_stats(client, django_user_model):
    user = django_user_model.objects.create_user(
        email="regular@example.com", username="regular", password=TEST_PASSWORD
    )
    client.force_login(user)

    response = client.get(stats_url())

    assert response.status_code == 403


@pytest.mark.django_db
def test_anonymous_user_cannot_get_draft_stats(client):
    response = client.get(stats_url())

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Route ordering: stats/ vs <int:pk>/
# ---------------------------------------------------------------------------

class TestRouteOrdering:
    def test_stats_path_resolves_to_stats_view(self):
        match = resolve("/api/event-drafts/stats/")
        assert match.url_name == "event-draft-stats"

    def test_numeric_pk_path_resolves_to_detail_view(self):
        match = resolve("/api/event-drafts/1/")
        assert match.url_name == "event-draft-detail"


# ---------------------------------------------------------------------------
# Staff guard on HTML views
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_anonymous_access_to_event_drafts_html_redirects(client):
    response = client.get("/event-drafts/")

    assert response.status_code == 302


@pytest.mark.django_db
def test_anonymous_access_to_event_draft_detail_html_redirects(client):
    response = client.get("/event-drafts/1/")

    assert response.status_code == 302


@pytest.mark.django_db
def test_non_staff_access_to_event_drafts_html_redirects(client, django_user_model):
    user = django_user_model.objects.create_user(
        email="regular@example.com", username="regular", password=TEST_PASSWORD
    )
    client.force_login(user)

    response = client.get("/event-drafts/")

    assert response.status_code == 302


@pytest.mark.django_db
def test_non_staff_access_to_event_draft_detail_html_redirects(client, django_user_model):
    user = django_user_model.objects.create_user(
        email="regular@example.com", username="regular", password=TEST_PASSWORD
    )
    client.force_login(user)

    response = client.get("/event-drafts/1/")

    assert response.status_code == 302


@pytest.mark.django_db
def test_staff_user_can_access_event_drafts_html(client, django_user_model):
    staff = django_user_model.objects.create_user(
        email="staffuser@example.com", username="staffuser", password=TEST_PASSWORD, is_staff=True
    )
    client.force_login(staff)

    response = client.get("/event-drafts/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_staff_user_can_access_event_draft_detail_html(client, django_user_model):
    staff = django_user_model.objects.create_user(
        email="staffuser@example.com", username="staffuser", password=TEST_PASSWORD, is_staff=True
    )
    client.force_login(staff)

    response = client.get("/event-drafts/1/")

    assert response.status_code == 200
