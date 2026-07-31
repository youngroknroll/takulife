"""base.html — 사이트 전역 django.contrib.messages 렌더링.

성공 메시지는 "error/warning -> error, 그 외 -> info"의 2분기 일반 규칙에
빠지지 않고 자기 전용 site-message-success 클래스로 렌더돼야 한다. 이건
공용 셸 변경(templates/base.html + static/css/base.css)이라 스태프
콘솔뿐 아니라 django.contrib.messages를 쓰는 모든 페이지에 영향을 준다 —
여기서 스태프 홈카테고리 POST를 쓰는 건 그게 구동하기 가장 간단한 기존
messages.success() 호출이기 때문일 뿐이다.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_성공_메시지는_site_message_success_클래스로_렌더링된다(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.post(
        "/staff/home-categories/",
        data={"feature_exhibition": "on", "order_exhibition": "1"},
        follow=True,
    )

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "site-message-success" in content
    assert "카테고리 설정이 저장되었습니다." in content
