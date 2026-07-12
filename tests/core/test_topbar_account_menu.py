"""core/partials/_topbar.html — the header account-menu's role-conditional
items. Rendered on every page; checked against the home page here since it
carries no auth/role logic of its own to confound the assertion.

The one invariant this whole track is built around — a staff account never
has a self-deletion path anywhere in the UI (accounts.views.delete_account
enforces this server-side too, see tests/auth/test_account_deletion.py) —
is asserted for all three roles below, not just the regular-member case.
"""
import pytest

MYPAGE_LINK = b'href="/mypage/"'
STAFF_CONSOLE_LINK = b'href="/staff/dashboard/"'
ADMIN_LINK = b'href="/admin/"'
DELETE_LINK = b'href="/accounts/delete/"'


@pytest.mark.django_db
def test_regular_member_sees_mypage_not_staff_console(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get("/")

    assert MYPAGE_LINK in response.content
    assert STAFF_CONSOLE_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_staff_member_sees_staff_console_not_mypage(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    response = client.get("/")

    assert STAFF_CONSOLE_LINK in response.content
    assert MYPAGE_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_superuser_sees_admin_link_in_addition_to_staff_console(client, make_user):
    superuser = make_user(is_staff=True, is_superuser=True)
    client.force_login(superuser)

    response = client.get("/")

    assert STAFF_CONSOLE_LINK in response.content
    assert ADMIN_LINK in response.content
    assert MYPAGE_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_anonymous_visitor_sees_neither_account_menu_branch(client):
    response = client.get("/")

    assert MYPAGE_LINK not in response.content
    assert STAFF_CONSOLE_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content
