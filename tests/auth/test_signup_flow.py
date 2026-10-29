"""회원가입 → 이메일 인증 → 리다이렉트로 이어지는 SSR 흐름, JSON API 아님."""

import re

import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_회원가입_후_이메일_인증을_완료하면_처음_요청한_next_경로로_리다이렉트된다(
    client, mailoutbox, valid_password
):
    resp = client.post(
        "/accounts/signup/?next=/archive/visits/",
        data={
            "email": "newcomer@example.com",
            "nickname": "newcomer닉",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )
    # 가입 자체는 "이메일을 확인하세요" 페이지에만 도착한다 — 인증 링크를
    # 클릭하기 전까지 세션은 부여되지 않는다(ACCOUNT_EMAIL_VERIFICATION=mandatory).
    assert resp.status_code == 302
    assert resp["Location"] == "/accounts/confirm-email/"

    assert len(mailoutbox) == 1
    match = re.search(r"http://\S+(/accounts/confirm-email/\S+/)", mailoutbox[0].body)
    assert match, mailoutbox[0].body

    confirm_resp = client.post(match.group(1))
    assert confirm_resp.status_code == 302
    assert confirm_resp["Location"] == "/archive/visits/"


# I18N-13
@pytest.mark.django_db
def test_가입_요청의_Accept_Language가_영어이면_인증_메일_제목이_영어다(
    client, mailoutbox, valid_password
):
    """번역이 채워지면 인증 메일 제목도 요청 언어를 따라야 한다."""
    client.post(
        "/accounts/signup/?next=/archive/visits/",
        data={
            "email": "english-signup@example.com",
            "nickname": "english닉",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert len(mailoutbox) == 1
    assert "Verify your email address" in mailoutbox[0].subject
