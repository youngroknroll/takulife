"""스태프 대시보드 주간 분석 요약 검증."""
import pytest

from core.models import AnalyticsEvent

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_대시보드는_주간_활성_사용자_수를_보여준다(staff_client):
    staff, client = staff_client()
    AnalyticsEvent.objects.create(
        event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user_key="user-a"
    )
    AnalyticsEvent.objects.create(
        event_name=AnalyticsEvent.EventName.EVENT_SEARCHED, user_key="user-a"
    )
    AnalyticsEvent.objects.create(
        event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user_key="user-b"
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "주간 활성 사용자" in content
    assert "2명" in content


@pytest.mark.django_db
def test_대시보드는_주간_이벤트_기록_건수를_보여준다(staff_client):
    staff, client = staff_client()
    for _ in range(3):
        AnalyticsEvent.objects.create(
            event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user_key="user-a"
        )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "주간 이벤트 기록" in content
    assert "3건" in content


@pytest.mark.django_db
def test_분석_이벤트가_없으면_대시보드는_0명_0건으로_표시한다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "주간 활성 사용자" in content
    assert "주간 이벤트 기록" in content
    assert "0명" in content
    assert "0건" in content
