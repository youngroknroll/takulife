"""accounts settings page (/accounts/settings/) — login gate + role-conditional
account-deletion link. Staff never sees the deletion link here, matching the
server-side 403 guard on accounts.views.delete_account itself (see
tests/auth/test_account_deletion.py) — UI hiding alone would not be enough,
but the two together keep the page consistent with what the view allows.
"""
import pytest

pytestmark = pytest.mark.web

SETTINGS_URL = "/accounts/settings/"
DELETE_LINK = b'href="/accounts/delete/"'


@pytest.mark.django_db
def test_비로그인_사용자가_설정_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get(SETTINGS_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_로그인_사용자가_설정_페이지에_접근하면_200으로_렌더링된다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_일반_사용자의_설정_페이지에는_계정_삭제_링크가_노출된다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert DELETE_LINK in response.content


@pytest.mark.django_db
def test_스태프의_설정_페이지에는_계정_삭제_링크가_노출되지_않는다(staff_client):
    _staff, logged_in_client = staff_client()

    response = logged_in_client.get(SETTINGS_URL)

    assert response.status_code == 200
    assert DELETE_LINK not in response.content
