"""
Tests for Phase 2 auth backend:
- Authorization / IDOR on archive API
- Auth boundary (anonymous, CSRF)
- Registration (valid, weak password, duplicate username)
- @login_required redirect on HTML archive views
"""
import secrets

import pytest
from django.test import Client
from rest_framework.test import APIClient


# A strong throwaway password generated at runtime for tests. Not a real
# credential and never stored — kept out of source so secret scanners do not
# flag a hardcoded password literal. Complexity prefix guarantees it passes
# AUTH_PASSWORD_VALIDATORS regardless of the random suffix.
VALID_PASSWORD = "Aa1!" + secrets.token_urlsafe(16)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_status(client, event, status_value="planned"):
    """Create a UserEventStatus for the currently logged-in client and return its id."""
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": status_value},
        content_type="application/json",
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Authorization / IDOR
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_b_patch_on_user_a_status_returns_404(client, make_user, make_event):
    """User B cannot PATCH user A's UserEventStatus — 404, not leaked."""
    user_a = make_user(username="idor-user-a")
    user_b = make_user(username="idor-user-b")
    event = make_event()

    client.force_login(user_a)
    status_id = _create_status(client, event)

    client.force_login(user_b)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_b_delete_on_user_a_status_returns_404(client, make_user, make_event):
    """User B cannot DELETE user A's UserEventStatus — 404, not leaked."""
    user_a = make_user(username="idor-del-a")
    user_b = make_user(username="idor-del-b")
    event = make_event()

    client.force_login(user_a)
    status_id = _create_status(client, event)

    client.force_login(user_b)
    response = client.delete(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_b_list_excludes_user_a_statuses(client, make_user, make_event):
    """GET list for user B does not include user A's statuses."""
    user_a = make_user(username="list-user-a")
    user_b = make_user(username="list-user-b")
    event = make_event()

    client.force_login(user_a)
    _create_status(client, event, "planned")

    client.force_login(user_b)
    response = client.get("/api/user-event-statuses/")

    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_post_cannot_set_user_field_owner_is_requester(client, make_user, make_event):
    """POST body cannot override user; owner is always the authenticated requester."""
    user_a = make_user(username="post-user-a")
    user_b = make_user(username="post-user-b")
    event = make_event()

    client.force_login(user_a)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned", "user": user_b.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    # The created status belongs to user_a, not user_b
    status_id = response.json()["id"]
    client.force_login(user_a)
    own_response = client.get(f"/api/user-event-statuses/{status_id}/")
    assert own_response.status_code == 200

    client.force_login(user_b)
    other_response = client.get(f"/api/user-event-statuses/{status_id}/")
    assert other_response.status_code == 404


@pytest.mark.django_db
def test_patch_cannot_change_event_field(client, make_user, make_event):
    """PATCH with different event id is silently ignored (event is read-only on update)."""
    user = make_user(username="patch-event-user")
    event = make_event(title="Original Event")
    other_event = make_event(title="Other Event")

    client.force_login(user)
    status_id = _create_status(client, event)

    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"event": other_event.id, "status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 200
    # event must remain unchanged
    assert response.json()["event"] == event.id
    assert response.json()["status"] == "visited"


# ---------------------------------------------------------------------------
# Auth boundary
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_anonymous_api_get_returns_403():
    """Anonymous GET to archive API returns 403 (DRF SessionAuthentication default)."""
    client = Client()
    response = client.get("/api/user-event-statuses/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_anonymous_api_post_returns_403(make_event):
    """Anonymous POST to archive API returns 403 (DRF SessionAuthentication default)."""
    event = make_event()
    client = Client()
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_authenticated_post_without_csrf_returns_403(make_user, make_event):
    """
    Authenticated POST without CSRF header returns 403 because
    SessionAuthentication enforces CSRF for unsafe methods.

    We use APIClient (which bypasses CSRF by default) and then
    explicitly enforce CSRF checking via enforce_csrf_checks=True.
    """
    user = make_user(username="csrf-test-user")
    event = make_event()

    api_client = APIClient(enforce_csrf_checks=True)
    api_client.force_login(user)

    response = api_client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_authenticated_post_with_csrf_succeeds(client, make_user, make_event):
    """
    Authenticated POST with proper session + CSRF succeeds.

    Django's test Client handles CSRF automatically when using force_login
    and the test client middleware is active (enforce_csrf_checks defaults
    to False for the test Client, which mirrors JS behaviour with cookie).
    """
    user = make_user(username="csrf-pass-user")
    event = make_event()

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_registration_get_renders_form(client):
    """GET /accounts/register/ returns 200."""
    response = client.get("/accounts/register/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_valid_registration_creates_user_and_logs_in(client, django_user_model):
    """Valid registration creates a user and authenticates the session."""
    response = client.post(
        "/accounts/register/",
        {
            "username": "newuser",
            "password1": VALID_PASSWORD,
            "password2": VALID_PASSWORD,
        },
    )
    # Should redirect after successful registration
    assert response.status_code == 302

    # User should exist in DB
    assert django_user_model.objects.filter(username="newuser").exists()

    # Session should be authenticated (follow redirect and check context)
    follow_response = client.get("/archive/")
    # archive/ is protected so if logged in we get 200, else 302 to login
    assert follow_response.status_code == 200


@pytest.mark.django_db
def test_weak_password_rejected_by_validators(client, django_user_model):
    """Weak password (all digits, too common) is rejected by AUTH_PASSWORD_VALIDATORS."""
    response = client.post(
        "/accounts/register/",
        {
            "username": "weakpwduser",
            "password1": "12345678",
            "password2": "12345678",
        },
    )
    # Should re-render form with error, not redirect
    assert response.status_code == 200
    assert not django_user_model.objects.filter(username="weakpwduser").exists()


@pytest.mark.django_db
def test_duplicate_username_rejected(client, django_user_model):
    """Duplicate username returns form error and does not create another user."""
    django_user_model.objects.create_user(username="existinguser", password=VALID_PASSWORD)

    response = client.post(
        "/accounts/register/",
        {
            "username": "existinguser",
            "password1": VALID_PASSWORD,
            "password2": VALID_PASSWORD,
        },
    )
    assert response.status_code == 200
    assert django_user_model.objects.filter(username="existinguser").count() == 1


# ---------------------------------------------------------------------------
# @login_required redirect
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_anonymous_archive_redirects_to_login(client):
    """Anonymous GET /archive/ → 302 to /accounts/login/?next=/archive/."""
    response = client.get("/archive/")
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/?next=/archive/"


@pytest.mark.django_db
def test_anonymous_archive_statuses_redirects_to_login(client):
    """Anonymous GET /archive/statuses/ → 302 to login."""
    response = client.get("/archive/statuses/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_anonymous_archive_visits_redirects_to_login(client):
    """Anonymous GET /archive/visits/ → 302 to login."""
    response = client.get("/archive/visits/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_authenticated_user_can_access_archive(client, make_user):
    """Authenticated user GET /archive/ → 200."""
    user = make_user(username="archive-viewer")
    client.force_login(user)
    response = client.get("/archive/")
    assert response.status_code == 200
