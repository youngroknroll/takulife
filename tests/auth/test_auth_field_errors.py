"""필드 오류가 실제 요소 옆에 뜨는지 검증한다. 정적 마크업이 아니라
실제 가입 거부 요청으로 오류를 발생시켜 확인한다."""
import pytest

pytestmark = pytest.mark.web

SIGNUP_URL = "/accounts/signup/"
LOGIN_URL = "/accounts/login/"


@pytest.mark.django_db
def test_약관_동의_없이_가입하면_해당_필드에_오류가_표시된다(client, valid_password):
    response = client.post(
        SIGNUP_URL,
        {
            "email": "noagreement2@example.com",
            "password1": valid_password,
            "password2": valid_password,
        },
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert '<ul class="field-error" id="id_terms_agreed-error">' in body
    assert "이용약관 및 개인정보처리방침에 동의해야 가입할 수 있습니다." in body


@pytest.mark.django_db
def test_비밀번호_확인이_일치하지_않으면_password2_필드에만_오류가_표시된다(client, valid_password):
    response = client.post(
        SIGNUP_URL,
        {
            "email": "mismatch@example.com",
            "password1": valid_password,
            "password2": valid_password + "x",
        },
    )

    assert response.status_code == 200
    body = response.content.decode()
    # 불일치 오류는 password2 소관이다. password1 자체는 유효하므로 오류 목록이 없어야 한다.
    assert 'id="id_password2-error"' in body
    assert 'id="id_password1-error"' not in body


@pytest.mark.django_db
def test_로그인_필드를_비워둔_채_제출하면_일반_오류_대신_필드별_오류가_표시된다(client):
    """빈 로그인/비밀번호가 실제 로그인 실패와 같은 일반 오류 문구를 띄우던 문제였다.
    아무 시도도 없었으므로 필드별 필수 오류만 떠야 한다."""
    response = client.post(LOGIN_URL, {"login": "", "password": ""})

    assert response.status_code == 200
    body = response.content.decode()
    assert "이메일 또는 비밀번호가 올바르지 않습니다" not in body
    assert 'id="id_login-error"' in body
    assert 'id="id_password-error"' in body


@pytest.mark.django_db
def test_로그인_자격_증명이_틀리면_필드별_오류_없이_일반_오류_문구만_표시된다(client, make_verified_user):
    make_verified_user(email="known@example.com")

    response = client.post(
        LOGIN_URL, {"login": "known@example.com", "password": "definitely-wrong"}
    )

    assert response.status_code == 200
    body = response.content.decode()
    # 문구만 검사하고 담는 요소(클래스명)는 고정하지 않는다. 리스킨으로 이미 한 번
    # 이름이 바뀌었다 (docs/FE/auth-editorial.md A13).
    assert "이메일 또는 비밀번호가 올바르지 않습니다." in body
    # 필드별 오류가 아니라 전체 오류이므로 개별 필드 오류 목록은 없어야 한다.
    assert 'id="id_login-error"' not in body
    assert 'id="id_password-error"' not in body
