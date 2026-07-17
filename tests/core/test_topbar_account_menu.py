"""core/partials/_topbar.html — the header account-menu's role-conditional
items. Rendered on every page; checked against the home page here since it
carries no auth/role logic of its own to confound the assertion.

The one invariant this whole track is built around — a staff account never
has a self-deletion path anywhere in the UI (accounts.views.delete_account
enforces this server-side too, see tests/auth/test_account_deletion.py) —
is asserted for all three roles below, not just the regular-member case.
"""
import pytest

pytestmark = pytest.mark.web

MYPAGE_LINK = b'href="/mypage/"'
STAFF_CONSOLE_LINK = b'href="/staff/dashboard/"'
SETTINGS_LINK = b'href="/accounts/settings/"'
ADMIN_LINK = b'href="/admin/"'
DELETE_LINK = b'href="/accounts/delete/"'


@pytest.mark.django_db
def test_일반_회원은_마이페이지만_보이고_스태프_콘솔은_보이지_않는다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get("/")

    assert MYPAGE_LINK in response.content
    assert STAFF_CONSOLE_LINK not in response.content
    assert SETTINGS_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_스태프_회원은_스태프_콘솔과_설정만_보이고_마이페이지는_보이지_않는다(client, make_user):
    """Staff has no mypage (no personal archive summary), so 설정 is the
    only click-reachable path to change email/password — without it staff
    could never reach account_change_password/account_email from the UI."""
    staff = make_user(is_staff=True)
    client.force_login(staff)

    response = client.get("/")

    assert STAFF_CONSOLE_LINK in response.content
    assert SETTINGS_LINK in response.content
    assert MYPAGE_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_슈퍼유저는_스태프_콘솔_설정에_더해_관리자_링크도_보인다(client, make_user):
    superuser = make_user(is_staff=True, is_superuser=True)
    client.force_login(superuser)

    response = client.get("/")

    assert STAFF_CONSOLE_LINK in response.content
    assert SETTINGS_LINK in response.content
    assert ADMIN_LINK in response.content
    assert MYPAGE_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_비로그인_방문자는_계정_메뉴_어느_분기도_보이지_않는다(client):
    response = client.get("/")

    assert MYPAGE_LINK not in response.content
    assert STAFF_CONSOLE_LINK not in response.content
    assert SETTINGS_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content
