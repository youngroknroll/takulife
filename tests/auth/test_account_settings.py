"""accounts settings page (/accounts/settings/) — login gate + role-conditional
account-deletion link. Staff never sees the deletion link here, matching the
server-side 403 guard on accounts.views.delete_account itself (see
tests/auth/test_account_deletion.py) — UI hiding alone would not be enough,
but the two together keep the page consistent with what the view allows.
"""
import pytest

SETTINGS_URL = "/accounts/settings/"
DELETE_LINK = b'href="/accounts/delete/"'


@pytest.mark.django_db
def test_anonymous_get_redirects_to_login(client):
    response = client.get(SETTINGS_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_authenticated_get_renders_200(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_regular_user_response_contains_delete_link(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert DELETE_LINK in response.content


@pytest.mark.django_db
def test_staff_user_response_does_not_contain_delete_link(staff_client):
    _staff, logged_in_client = staff_client()

    response = logged_in_client.get(SETTINGS_URL)

    assert response.status_code == 200
    assert DELETE_LINK not in response.content
