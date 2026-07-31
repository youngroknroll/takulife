"""core/partials/_topbar.html — 헤더 계정 메뉴의 역할별 조건부 항목. 모든
페이지에서 렌더되며, 여기서는 홈 페이지로 검증한다 — 홈은 인증/역할 로직이
없어 단언을 흐리지 않는다.

이 트랙 전체가 지키려는 단 하나의 불변 조건 — 스태프 계정은 UI 어디에도
자기 탈퇴 경로가 없다(accounts.views.delete_account가 서버 쪽에서도
강제한다, tests/auth/test_account_deletion.py 참고) — 를 일반 회원뿐 아니라
아래 세 역할 모두에 대해 검증한다.
"""
import pytest

pytestmark = pytest.mark.web

MYPAGE_LINK = b'href="/mypage/"'
STAFF_CONSOLE_LINK = b'href="/staff/dashboard/"'
SETTINGS_LINK = b'href="/accounts/settings/"'
ADMIN_LINK = b'href="/admin/"'
DELETE_LINK = b'href="/accounts/delete/"'


@pytest.mark.django_db
def test_일반_회원은_마이페이지만_보이고_스태프_콘솔은_보이지_않는다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get("/")

    assert MYPAGE_LINK in response.content
    assert STAFF_CONSOLE_LINK not in response.content
    assert SETTINGS_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_스태프_회원은_스태프_콘솔과_설정만_보이고_마이페이지는_보이지_않는다(client, make_user):
    """스태프는 마이페이지(개인 아카이브 요약)가 없으므로 이메일/비밀번호를
    바꾸려면 설정이 클릭으로 닿을 수 있는 유일한 경로다 — 이게 없으면
    스태프는 UI로 account_change_password/account_email에 절대 못
    닿는다."""
    staff = make_user(is_staff=True)
    client.force_login(staff)

    response = client.get("/")

    assert STAFF_CONSOLE_LINK in response.content
    assert SETTINGS_LINK in response.content
    assert MYPAGE_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_슈퍼유저는_스태프_콘솔_설정에_더해_관리자_링크도_보인다(client, make_user):
    superuser = make_user(is_staff=True, is_superuser=True)
    client.force_login(superuser)

    response = client.get("/")

    assert STAFF_CONSOLE_LINK in response.content
    assert SETTINGS_LINK in response.content
    assert ADMIN_LINK in response.content
    assert MYPAGE_LINK not in response.content
    assert DELETE_LINK not in response.content


@pytest.mark.django_db
def test_비로그인_방문자는_계정_메뉴_어느_분기도_보이지_않는다(client):
    response = client.get("/")

    assert MYPAGE_LINK not in response.content
    assert STAFF_CONSOLE_LINK not in response.content
    assert SETTINGS_LINK not in response.content
    assert ADMIN_LINK not in response.content
    assert DELETE_LINK not in response.content
