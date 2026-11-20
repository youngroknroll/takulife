"""예전 PBKDF2 해시 사용자의 로그인·세션이 Argon2 전환 중에도 그대로
동작하는지 지킨다.
"""

from datetime import timedelta
import secrets

from django.contrib.auth.hashers import make_password
from django.test import override_settings
from django.utils import timezone
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


@pytest.mark.django_db
def test_비밀번호_변경_화면에서_현재_비밀번호를_확인해도_새_비밀번호가_거부되면_다음_요청까지_로그인_상태가_유지된다(
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

        # When: 새 비밀번호 두 칸이 달라 폼이 거부된다.
        새_비밀번호1 = "Np-" + secrets.token_urlsafe(16)
        새_비밀번호2 = "Np-" + secrets.token_urlsafe(16)
        response = client.post(
            "/accounts/password/change/",
            {
                "oldpassword": valid_password,
                "password1": 새_비밀번호1,
                "password2": 새_비밀번호2,
            },
        )

        # Then: 폼이 다시 그려진다.
        assert response.status_code == 200

    # Then: 다음 요청에서도 같은 client로 로그인 상태가 유지된다.
    response = client.get("/accounts/settings/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_틀린_비밀번호로_로그인하면_실패하고_해시는_그대로다(
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

        # When: 틀린 비밀번호로 로그인을 시도한다.
        response = client.post(
            "/accounts/login/", {"login": user.email, "password": "definitely-wrong"}
        )

        # Then: 로그인은 거부되고 저장된 해시도 그대로다.
        assert response.status_code == 200
        # 다른 이유의 200(예: 잠금 화면)과 구별한다.
        body = response.content.decode()
        assert "이메일 또는 비밀번호가 올바르지 않습니다." in body
        user.refresh_from_db()
        assert user.password.startswith("pbkdf2_sha256$")


@pytest.mark.django_db
def test_로그인_중_해시가_바뀌어도_password_changed_at은_그대로다(
    client,
    make_verified_user,
    valid_password,
    production_password_hashers,
):
    # Given: password_changed_at에 과거 시각을 심는다. 기본값 None이면
    # 아무 경로도 안 건드린 것과 구별이 안 되기 때문이다.
    user = make_verified_user()
    심어둔_시각 = timezone.now() - timedelta(days=5)
    user.password_changed_at = 심어둔_시각
    user.save(update_fields=["password_changed_at"])
    with override_settings(PASSWORD_HASHERS=production_password_hashers):
        user.password = make_password(valid_password, hasher="pbkdf2_sha256")
        user.save(update_fields=["password"])

        # When: 올바른 비밀번호로 로그인한다.
        response = client.post(
            "/accounts/login/", {"login": user.email, "password": valid_password}
        )

        # Then: 로그인은 성공하고 해시도 Argon2id로 바뀐다(전제 확인).
        assert response.status_code == 302
        user.refresh_from_db()
        assert user.password.startswith("argon2$argon2id$")

    # Then: 해시 전환만으로는 password_changed_at이 바뀌지 않는다.
    assert user.password_changed_at == 심어둔_시각
