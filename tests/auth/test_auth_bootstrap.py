import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from core.auth_views import me


@pytest.mark.web
def test_비로그인_사용자의_내_정보_조회는_401_또는_403으로_거부된다(client):
    response = client.get("/api/auth/me/")

    assert response.status_code in (401, 403)


@pytest.mark.contract
def test_인증_사용자_모델_설정은_커스텀_User_모델로_고정된다(settings):
    assert settings.AUTH_USER_MODEL == "accounts.User"


@pytest.mark.django_db
@pytest.mark.contract
def test_내_정보_조회는_DB를_다시_조회하지_않고_인증된_요청_사용자_정보를_그대로_반환한다():
    request = APIRequestFactory().get("/api/auth/me/")
    user = User(email="tester@example.com", is_staff=True)

    force_authenticate(request, user=user)
    response = me(request)

    assert response.status_code == 200
    assert response.data == {
        "id": None,
        "email": "tester@example.com",
        "is_staff": True,
    }
