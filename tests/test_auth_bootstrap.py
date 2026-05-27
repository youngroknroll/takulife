import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from core.auth_views import me


def test_auth_me_requires_login(client):
    response = client.get("/api/auth/me/")

    assert response.status_code in (401, 403)


def test_auth_model_setting_is_custom_user(settings):
    assert settings.AUTH_USER_MODEL == "accounts.User"


@pytest.mark.django_db
def test_auth_me_returns_authenticated_user_without_reloading_from_database():
    request = APIRequestFactory().get("/api/auth/me/")
    user = User(username="tester", email="tester@example.com", is_staff=True)

    force_authenticate(request, user=user)
    response = me(request)

    assert response.status_code == 200
    assert response.data == {
        "id": None,
        "username": "tester",
        "email": "tester@example.com",
        "is_staff": True,
    }
