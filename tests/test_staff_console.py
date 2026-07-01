"""Staff Console (/staff/) — PR-1a: auth pin, console gate, dashboard, redirects."""
import base64
import secrets
import string

import pytest

from drafts.models import EventDraft


def _password():
    """Runtime password with guaranteed complexity, no literal in source."""
    return (
        secrets.choice(string.ascii_uppercase)
        + secrets.choice(string.ascii_lowercase)
        + secrets.choice(string.digits)
        + secrets.token_urlsafe(16)
    )


def _basic_auth(email, password):
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return f"Basic {token}"


@pytest.mark.django_db
def test_staff_api_rejects_http_basic_auth(client, make_user):
    """HTTP Basic auth must NOT authenticate against staff DRF endpoints — Basic
    bypasses CSRF, so only SessionAuthentication is accepted. A valid staff
    credential sent via Basic is treated as unauthenticated (403)."""
    password = _password()
    staff = make_user(password=password, is_staff=True)

    resp = client.get(
        "/api/event-drafts/stats/",
        HTTP_AUTHORIZATION=_basic_auth(staff.email, password),
    )

    assert resp.status_code == 403, resp.status_code


# ---------------------------------------------------------------------------
# Console gate (staff_console_required)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_anonymous_dashboard_redirects_to_accounts_login(client):
    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 302
    assert resp.url == "/accounts/login/?next=/staff/dashboard/"


@pytest.mark.django_db
def test_non_staff_dashboard_returns_403(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_authenticated_non_staff_does_not_redirect_loop(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/dashboard/", follow=True)

    assert len(resp.redirect_chain) <= 1
    assert resp.status_code == 403


@pytest.mark.django_db
def test_authenticated_non_staff_gets_403_not_login_bounce(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_anonymous_still_redirects_to_login_not_403(client):
    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 302
    assert resp.url == "/accounts/login/?next=/staff/dashboard/"


@pytest.mark.django_db
def test_staff_dashboard_returns_200_with_pending_count(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)
    EventDraft.objects.create(
        source_url="https://example.com/a",
        extracted_title="드래프트 A",
        review_status=EventDraft.ReviewStatus.PENDING,
    )
    EventDraft.objects.create(
        source_url="https://example.com/b",
        extracted_title="드래프트 B",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["pending_count"] == 1


@pytest.mark.django_db
def test_staff_root_redirects_to_dashboard(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.get("/staff/")

    assert resp.status_code == 302
    assert resp.url == "/staff/dashboard/"


# ---------------------------------------------------------------------------
# Relocation + backward-compat redirects
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_old_drafts_list_url_redirects_to_new_path(client):
    resp = client.get("/event-drafts/")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/"


@pytest.mark.django_db
def test_old_drafts_list_url_preserves_next_query_string(client):
    resp = client.get("/event-drafts/?next=/x")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/?next=/x"


@pytest.mark.django_db
def test_old_drafts_detail_url_redirects_to_new_path(client):
    resp = client.get("/event-drafts/5/")

    assert resp.status_code == 302
    assert resp.url == "/staff/drafts/5/"


@pytest.mark.django_db
def test_staff_can_access_new_drafts_list_url(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.get("/staff/drafts/")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_staff_can_access_new_draft_detail_url(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)
    draft = EventDraft.objects.create(
        source_url="https://example.com/c", extracted_title="드래프트 C"
    )

    resp = client.get(f"/staff/drafts/{draft.id}/")

    assert resp.status_code == 200


@pytest.mark.django_db
def test_staff_can_access_home_categories_url(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.get("/staff/home-categories/")

    assert resp.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/staff/dashboard/",
        "/staff/drafts/",
        "/staff/drafts/1/",
        "/staff/home-categories/",
    ],
)
def test_non_staff_blocked_from_new_staff_paths(client, make_user, path):
    user = make_user()
    client.force_login(user)

    resp = client.get(path)

    assert resp.status_code == 403
