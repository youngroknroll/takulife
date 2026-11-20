"""비밀번호 변경 화면이 현재 비밀번호 확인을 통과해야만 비밀번호를
바꾸는지 지킨다(`accounts.forms.PasswordChangeForm`).
"""

import secrets

import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_비밀번호_변경에서_현재_비밀번호가_틀리면_비밀번호가_바뀌지_않는다(
    client, make_verified_user, valid_password
):
    # Given: 테스트 기본 해셔로 로그인 상태를 만든다.
    user = make_verified_user(password=valid_password)
    client.force_login(user)

    # When: 새 비밀번호는 맞게 넣어 실패 원인을 현재 비밀번호 하나로 좁힌다.
    새_비밀번호 = "Np-" + secrets.token_urlsafe(16)
    response = client.post(
        "/accounts/password/change/",
        {"oldpassword": "definitely-wrong", "password1": 새_비밀번호, "password2": 새_비밀번호},
    )

    # Then: 현재 비밀번호 확인에서 막혀 아무것도 바뀌지 않았다.
    assert response.status_code == 200
    body = response.content.decode()
    assert 'id="id_oldpassword-error"' in body
    assert "현재 비밀번호를 입력하세요." in body
    user.refresh_from_db()
    assert user.check_password(valid_password)
    assert user.password_changed_at is None
