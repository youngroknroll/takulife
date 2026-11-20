"""예전 PBKDF2 해시 사용자의 로그인·세션이 Argon2 전환 중에도 그대로
동작하는지 지킨다.
"""

from django.contrib.auth.hashers import make_password
from django.test import override_settings
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_기존_pbkdf2_해시_사용자가_로그인에_성공하면_해시가_argon2id로_바뀐다(
    client,
    make_verified_user,
    valid_password,
    production_password_hashers,
):
    # Given: 운영 해셔 목록을 적용한 상태에서 사용자 비밀번호를 예전
    # PBKDF2 해시로 바꿔 저장한다.
    user = make_verified_user()
    with override_settings(PASSWORD_HASHERS=production_password_hashers):
        user.password = make_password(valid_password, hasher="pbkdf2_sha256")
        user.save(update_fields=["password"])

        # Given 확인: 저장된 해시가 실제로 PBKDF2다.
        assert user.password.startswith("pbkdf2_sha256$")

        # When: PBKDF2 해시로 저장된 비밀번호 그대로 로그인한다.
        response = client.post(
            "/accounts/login/", {"login": user.email, "password": valid_password}
        )

        # Then: 로그인은 그대로 성공해 컬렉션 페이지로 이동한다.
        assert response.status_code == 302
        assert response.url == "/collection/"

    # Then: 로그인 과정에서 해시가 Argon2id로 바뀌어 저장된다.
    user.refresh_from_db()
    assert user.password.startswith("argon2$argon2id$")


@pytest.mark.django_db
def test_이메일_변경_화면에서_현재_비밀번호를_확인해도_다음_요청까지_로그인_상태가_유지된다(
    client,
    make_verified_user,
    valid_password,
    production_password_hashers,
):
    # Given: 운영 해셔 목록을 적용한 상태에서 사용자 비밀번호를 예전
    # PBKDF2 해시로 저장하고, 로그인 POST 없이(해시를 바꾸므로) 세션만
    # force_login으로 연다.
    user = make_verified_user()
    with override_settings(PASSWORD_HASHERS=production_password_hashers):
        user.password = make_password(valid_password, hasher="pbkdf2_sha256")
        user.save(update_fields=["password"])
        client.force_login(user)

        # When: 이메일 변경 화면에서 현재 비밀번호를 확인시키며 제출한다.
        response = client.post(
            "/accounts/email/",
            {
                "action_add": "",
                "email": "new-address@example.com",
                "current_password": valid_password,
            },
        )

        # Then: 이메일 변경 제출이 받아들여진다.
        assert response.status_code == 302

    # Then: 다음 요청에서도 같은 client로 로그인 상태가 유지된다.
    response = client.get("/accounts/settings/")
    assert response.status_code == 200
