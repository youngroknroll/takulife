"""
Tests for Phase 2 auth backend:
- Authorization / IDOR on archive API
- Auth boundary (anonymous, CSRF)
- Registration (valid, weak password, duplicate email, mandatory email
  verification via django-allauth)
- @login_required redirect on HTML archive views
"""
import re

import pytest
from django.test import Client
from rest_framework.test import APIClient


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
# Registration (django-allauth: email identifier, mandatory verification)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_registration_get_renders_form(client):
    """GET /accounts/signup/ returns 200."""
    response = client.get("/accounts/signup/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_valid_registration_does_not_log_in_before_verification(client, django_user_model, valid_password):
    """Signup creates an unverified user and does NOT grant a session yet."""
    response = client.post(
        "/accounts/signup/",
        {
            "email": "newuser@example.com",
            "password1": valid_password,
            "password2": valid_password,
        },
    )
    # Redirects to the "check your email" page, not straight into the app.
    assert response.status_code == 302
    assert django_user_model.objects.filter(email="newuser@example.com").exists()

    # Not authenticated yet — protected pages still bounce to login.
    archive_response = client.get("/archive/")
    assert archive_response.status_code == 302
    assert "/accounts/login/" in archive_response["Location"]


@pytest.mark.django_db
def test_confirming_email_logs_the_user_in(client, django_user_model, mailoutbox, valid_password):
    """Clicking the emailed confirmation link authenticates the session."""
    client.post(
        "/accounts/signup/",
        {
            "email": "confirmme@example.com",
            "password1": valid_password,
            "password2": valid_password,
        },
    )
    assert len(mailoutbox) == 1
    match = re.search(r"http://\S+(/accounts/confirm-email/\S+/)", mailoutbox[0].body)
    assert match, mailoutbox[0].body

    response = client.post(match.group(1), follow=True)
    assert response.status_code == 200

    archive_response = client.get("/archive/")
    assert archive_response.status_code == 200


@pytest.mark.django_db
def test_weak_password_rejected_by_validators(client, django_user_model):
    """Weak password (all digits, too common) is rejected by AUTH_PASSWORD_VALIDATORS."""
    response = client.post(
        "/accounts/signup/",
        {
            "email": "weakpwduser@example.com",
            "password1": "12345678",
            "password2": "12345678",
        },
    )
    # Should re-render form with error, not redirect
    assert response.status_code == 200
    assert not django_user_model.objects.filter(email="weakpwduser@example.com").exists()


@pytest.mark.django_db
def test_duplicate_email_rejected(client, django_user_model, mailoutbox, valid_password):
    """Signing up with an existing email does not create a second account.

    django-allauth's default ACCOUNT_PREVENT_ENUMERATION=True responds with
    the same redirect as a fresh signup (so the response can't be used to
    probe which emails are registered) but notifies the existing account
    by mail instead of creating a duplicate user.
    """
    django_user_model.objects.create_user(email="existinguser@example.com", password=valid_password)

    response = client.post(
        "/accounts/signup/",
        {
            "email": "existinguser@example.com",
            "password1": valid_password,
            "password2": valid_password,
        },
    )
    assert response.status_code == 302
    assert django_user_model.objects.filter(email="existinguser@example.com").count() == 1
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["existinguser@example.com"]


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


# ---------------------------------------------------------------------------
# next preservation across login <-> signup links
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_login_page_signup_link_preserves_next(client):
    """GET /accounts/login/?next=X renders a signup link carrying next=X."""
    response = client.get("/accounts/login/?next=/archive/")
    assert response.status_code == 200
    assert b'href="/accounts/signup/?next=%2Farchive%2F"' in response.content


@pytest.mark.django_db
def test_signup_page_login_link_preserves_next(client):
    """GET /accounts/signup/?next=X renders a login link carrying next=X."""
    response = client.get("/accounts/signup/?next=/archive/")
    assert response.status_code == 200
    assert b'href="/accounts/login/?next=%2Farchive%2F"' in response.content


@pytest.mark.django_db
def test_login_page_signup_link_omits_next_when_absent(client):
    """GET /accounts/login/ without next renders a bare signup link."""
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert b'href="/accounts/signup/"' in response.content
