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

pytestmark = pytest.mark.web


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
def test_다른_사용자의_일정_상태를_PATCH하면_404로_숨겨진다(client, make_user, make_event):
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
def test_다른_사용자의_일정_상태를_DELETE하면_404로_숨겨진다(client, make_user, make_event):
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
def test_일정_상태_목록_조회는_다른_사용자의_기록을_포함하지_않는다(client, make_user, make_event):
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
def test_일정_상태_생성_시_user_필드를_지정해도_소유자는_요청자로_고정된다(client, make_user, make_event):
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
def test_일정_상태_수정_시_event_필드_변경_요청은_무시된다(client, make_user, make_event):
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
def test_비로그인_사용자의_일정_상태_API_조회는_403으로_거부된다():
    """Anonymous GET to archive API returns 403 (DRF SessionAuthentication default)."""
    client = Client()
    response = client.get("/api/user-event-statuses/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_비로그인_사용자의_일정_상태_API_생성_요청은_403으로_거부된다(make_event):
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
def test_CSRF_토큰_없이_일정_상태를_생성하면_403으로_거부된다(make_user, make_event):
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
def test_CSRF_토큰과_함께_일정_상태를_생성하면_201로_성공한다(client, make_user, make_event):
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
def test_회원가입_페이지에_접근하면_가입_폼이_렌더링된다(client):
    """GET /accounts/signup/ returns 200."""
    response = client.get("/accounts/signup/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_회원가입_직후에는_이메일_인증_전이라_로그인_상태가_되지_않는다(client, django_user_model, valid_password):
    """Signup creates an unverified user and does NOT grant a session yet."""
    response = client.post(
        "/accounts/signup/",
        {
            "email": "newuser@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
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
def test_이메일_인증_링크를_클릭하면_로그인_상태가_된다(client, django_user_model, mailoutbox, valid_password):
    """Clicking the emailed confirmation link authenticates the session."""
    client.post(
        "/accounts/signup/",
        {
            "email": "confirmme@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
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
def test_취약한_비밀번호로_가입하면_거부되고_계정이_생성되지_않는다(client, django_user_model):
    """Weak password (all digits, too common) is rejected by AUTH_PASSWORD_VALIDATORS."""
    response = client.post(
        "/accounts/signup/",
        {
            "email": "weakpwduser@example.com",
            "password1": "12345678",
            "password2": "12345678",
            "terms_agreed": "on",
        },
    )
    # Should re-render form with error, not redirect
    assert response.status_code == 200
    assert not django_user_model.objects.filter(email="weakpwduser@example.com").exists()


@pytest.mark.django_db
def test_이미_가입된_이메일로_다시_가입해도_중복_계정이_생성되지_않는다(client, django_user_model, mailoutbox, valid_password):
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
            "terms_agreed": "on",
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
def test_비로그인_사용자가_아카이브에_접근하면_next_파라미터와_함께_로그인_페이지로_리다이렉트된다(client):
    """Anonymous GET /archive/ → 302 to /accounts/login/?next=/archive/."""
    response = client.get("/archive/")
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/?next=/archive/"


@pytest.mark.django_db
def test_비로그인_사용자가_나의_일정_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    """Anonymous GET /archive/statuses/ → 302 to login."""
    response = client.get("/archive/statuses/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_비로그인_사용자가_다녀온_기록_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    """Anonymous GET /archive/visits/ → 302 to login."""
    response = client.get("/archive/visits/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_로그인_사용자는_아카이브_페이지에_접근할_수_있다(client, make_user):
    """Authenticated user GET /archive/ → 200."""
    user = make_user(username="archive-viewer")
    client.force_login(user)
    response = client.get("/archive/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# next preservation across login <-> signup links
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_next_파라미터가_있는_로그인_페이지의_가입_링크는_next를_유지한다(client):
    """GET /accounts/login/?next=X renders a signup link carrying next=X."""
    response = client.get("/accounts/login/?next=/archive/")
    assert response.status_code == 200
    assert b'href="/accounts/signup/?next=%2Farchive%2F"' in response.content


@pytest.mark.django_db
def test_next_파라미터가_있는_가입_페이지의_로그인_링크는_next를_유지한다(client):
    """GET /accounts/signup/?next=X renders a login link carrying next=X."""
    response = client.get("/accounts/signup/?next=/archive/")
    assert response.status_code == 200
    assert b'href="/accounts/login/?next=%2Farchive%2F"' in response.content


@pytest.mark.django_db
def test_next_파라미터가_없는_로그인_페이지의_가입_링크는_next_없이_생성된다(client):
    """GET /accounts/login/ without next renders a bare signup link."""
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert b'href="/accounts/signup/"' in response.content
