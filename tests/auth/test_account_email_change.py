"""accounts.forms.EmailChangeForm — ACCOUNT_CHANGE_EMAIL 흐름에서 현재
비밀번호 재확인을 강제하는 커스텀 add_email 폼 (계정 설정 계획서 B2/B3,
account-settings-editorial 계획서 AS-3~AS-5).

AS-3은 폼 자체의 유효성 판정(domain)만 보고, AS-4/AS-5는 실제
/accounts/email/ POST를 거쳐 그 판정이 EmailAddress 부작용을 실제로
막는지/allauth의 CHANGE_EMAIL 치환 규약이 살아있는지 본다(web).
"""
import pytest
from allauth.account.models import EmailAddress

from accounts.forms import EmailChangeForm

EMAIL_URL = "/accounts/email/"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "use_correct_password, expected_valid",
    [
        pytest.param(True, True, id="올바른_비밀번호"),
        pytest.param(False, False, id="잘못된_비밀번호"),
    ],
)
def test_이메일_변경_폼은_현재_비밀번호가_맞을_때만_유효하다(
    use_correct_password, expected_valid, make_user, valid_password
):
    user = make_user(password=valid_password)
    submitted_password = valid_password if use_correct_password else "definitely-wrong"

    form = EmailChangeForm(
        data={"email": "changed@example.com", "current_password": submitted_password},
        user=user,
    )

    assert form.is_valid() is expected_valid


@pytest.mark.django_db
@pytest.mark.web
def test_잘못된_현재_비밀번호로_이메일_변경을_요청하면_이메일_주소_집합이_변하지_않는다(
    client, make_verified_user, valid_password
):
    user = make_verified_user(password=valid_password)
    before = set(
        EmailAddress.objects.filter(user=user).values_list("email", "verified", "primary")
    )
    client.force_login(user)

    response = client.post(
        EMAIL_URL,
        {
            "action_add": "",
            "email": "new-address@example.com",
            "current_password": "definitely-wrong",
        },
    )

    assert response.status_code == 200
    after = set(
        EmailAddress.objects.filter(user=user).values_list("email", "verified", "primary")
    )
    assert after == before


@pytest.mark.django_db
@pytest.mark.web
def test_이메일_변경을_연속으로_두_번_요청하면_미인증_주소는_최신_1건만_남는다(
    client, make_verified_user, valid_password
):
    user = make_verified_user(password=valid_password)
    client.force_login(user)

    first_response = client.post(
        EMAIL_URL,
        {
            "action_add": "",
            "email": "first-change@example.com",
            "current_password": valid_password,
        },
    )
    second_response = client.post(
        EMAIL_URL,
        {
            "action_add": "",
            "email": "second-change@example.com",
            "current_password": valid_password,
        },
    )

    assert first_response.status_code == 302
    assert second_response.status_code == 302
    unverified = EmailAddress.objects.filter(user=user, verified=False)
    assert unverified.count() == 1
    assert unverified.get().email == "second-change@example.com"
