"""base.html — site-wide django.contrib.messages rendering (PR-D1 item 5).

A success message must render with its own site-message-success class
instead of falling into the generic "error/warning -> error, else -> info"
2-way switch. This is a shared-chrome change (templates/base.html +
static/css/base.css) — it affects every page that uses
django.contrib.messages, not just the staff console; the staff
home-categories POST is used here only because it is the simplest existing
messages.success() call to drive.
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
