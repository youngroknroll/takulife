"""계정 설정 페이지(/accounts/settings/) — 로그인 게이트 + 역할별 조건부
계정 삭제 링크. 스태프는 여기서 삭제 링크를 절대 못 보는데, 이는
accounts.views.delete_account 자체의 서버 쪽 403 가드와 일치한다
(tests/auth/test_account_deletion.py 참고) — UI에서 숨기는 것만으로는
부족하지만, 둘을 합치면 페이지가 뷰가 허용하는 범위와 일관되게 유지된다.
"""
import datetime as dt

import pytest
from django.utils import timezone

pytestmark = pytest.mark.web

SETTINGS_URL = "/accounts/settings/"
DELETE_LINK = b'href="/accounts/delete/"'


@pytest.mark.django_db
def test_비로그인_사용자가_설정_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get(SETTINGS_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_로그인_사용자가_설정_페이지에_접근하면_200으로_렌더링된다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_일반_사용자의_설정_페이지에는_계정_삭제_링크가_노출된다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert DELETE_LINK in response.content


@pytest.mark.django_db
def test_스태프의_설정_페이지에는_계정_삭제_링크가_노출되지_않는다(staff_client):
    _staff, logged_in_client = staff_client()

    response = logged_in_client.get(SETTINGS_URL)

    assert response.status_code == 200
    assert DELETE_LINK not in response.content


# ---------------------------------------------------------------------------
# 개요 컨텍스트 (AS-6~AS-8, account-settings-editorial 계획서 B4)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_인증완료_사용자가_설정_페이지에_접근하면_개요_컨텍스트에_이메일_인증여부_가입일이_담긴다(
    client, make_verified_user
):
    """make_verified_user만 EmailAddress 행을 만든다 — 인증됨 분기는 이
    픽스처로만 실제로 실행된다(계획서 픽스처 함정 1번)."""
    user = make_verified_user()
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert response.context["account_email"] == user.email
    assert response.context["email_verified"] is True
    assert response.context["date_joined"] == user.date_joined


@pytest.mark.django_db
def test_이메일_인증_행이_없는_사용자가_설정_페이지에_접근하면_200이며_미인증으로_표시된다(
    client, make_user
):
    """make_user는 EmailAddress 행을 만들지 않는다 — null 분기는 이
    픽스처로만 실제로 실행된다(계획서 픽스처 함정 1번)."""
    user = make_user()
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert response.status_code == 200
    assert response.context["email_verified"] is False


@pytest.mark.django_db
def test_비밀번호_변경_이력이_있으면_설정_페이지의_변경일_표시가_UTC가_아닌_로컬_타임존_날짜를_따른다(
    client, make_user
):
    """password_changed_at은 UTC aware datetime으로 저장되므로, 화면 표시는
    settings.TIME_ZONE(Asia/Seoul) 기준 날짜여야 한다(마이페이지의 동일 규칙,
    tests/core/test_mypage_view.py와 동일 패턴)."""
    user = make_user()
    utc_changed_at = timezone.now().astimezone(dt.timezone.utc).replace(
        hour=23, minute=0, second=0, microsecond=0
    )
    user.password_changed_at = utc_changed_at
    user.save(update_fields=["password_changed_at"])
    expected_local_date = timezone.localtime(utc_changed_at).date()
    assert expected_local_date != utc_changed_at.date()  # 시간대 경계 확인
    client.force_login(user)

    response = client.get(SETTINGS_URL)

    assert response.context["password_changed_display"] == expected_local_date.strftime(
        "%Y.%m.%d"
    )
