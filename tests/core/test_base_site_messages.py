"""django.contrib.messages가 두 셸 각각에서 렌더링되는지 본다.

성공 메시지는 "error/warning -> error, 그 외 -> info"의 2분기에 빠지지 않고
자기 전용 클래스로 나와야 한다. 스태프 콘솔이 base.html에서 떨어져 나가면서
셸이 둘이 됐고 각자 자기 클래스를 쓴다 — 한쪽만 검사하면 다른 쪽이 조용히
메시지를 잃어도 통과한다.
"""
import pytest
from django.utils import timezone


from accounts.services import DELETION_GRACE_PERIOD

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_소비자_셸의_성공_메시지는_site_message_success_클래스로_렌더링된다(
    client, make_verified_user, valid_password
):
    # 비밀번호 리터럴을 소스에 두면 시크릿 스캐너가 잡는다. make_verified_user는
    # EmailAddress까지 만들어 준다 — 없으면 allauth가 로그인을 막아 탈퇴 취소
    # 신호 자체가 돌지 않는다.
    user = make_verified_user()
    password = valid_password
    user.deletion_requested_at = timezone.now() - DELETION_GRACE_PERIOD / 2
    user.save(update_fields=["deletion_requested_at"])

    resp = client.post(
        "/accounts/login/",
        data={"login": user.email, "password": password},
        follow=True,
    )

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "site-message-success" in content
    assert "탈퇴 예약이 취소되었습니다." in content


@pytest.mark.django_db
def test_스태프_셸의_성공_메시지는_staff_message_success_클래스로_렌더링된다(
    client, make_user
):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.post(
        "/staff/home-categories/",
        data={"feature_exhibition": "on", "order_exhibition": "1"},
        follow=True,
    )

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "staff-message-success" in content
    assert "카테고리 설정이 저장되었습니다." in content
