"""Auth form field errors render next to their own input. Reuses the
existing signup-rejection POST from test_signup_terms_agreement.py to
actually trigger a field error rather than asserting against static markup.
"""
import pytest

SIGNUP_URL = "/accounts/signup/"
LOGIN_URL = "/accounts/login/"


@pytest.mark.django_db
def test_signup_missing_terms_shows_field_error(client, valid_password):
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
def test_signup_password_mismatch_error_targets_password2_only(client, valid_password):
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
    # The mismatch error belongs to password2 — password1 itself is valid
    # and must not get an error list of its own.
    assert 'id="id_password2-error"' in body
    assert 'id="id_password1-error"' not in body


@pytest.mark.django_db
def test_login_blank_fields_show_field_errors_not_generic_message(client):
    """Blank login/password used to trigger the same generic "wrong
    credentials" copy as an actual failed login — misleading, since nothing
    was even attempted yet. Field-level required errors should show
    instead, and the generic alert should not."""
    response = client.post(LOGIN_URL, {"login": "", "password": ""})

    assert response.status_code == 200
    body = response.content.decode()
    assert "이메일 또는 비밀번호가 올바르지 않습니다" not in body
    assert 'id="id_login-error"' in body
    assert 'id="id_password-error"' in body


@pytest.mark.django_db
def test_login_wrong_credentials_shows_generic_alert_only(client, make_verified_user):
    make_verified_user(email="known@example.com")

    response = client.post(
        LOGIN_URL, {"login": "known@example.com", "password": "definitely-wrong"}
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert '<p class="auth-error">이메일 또는 비밀번호가 올바르지 않습니다.</p>' in body
    # Neither field is individually invalid here (this is a non-field
    # error), so neither should get its own error list.
    assert 'id="id_login-error"' not in body
    assert 'id="id_password-error"' not in body
