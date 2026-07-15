"""Staff dashboard weekly analytics summary (PR-0e checkpoint B14).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest

from core.models import AnalyticsEvent


@pytest.mark.django_db
def test_staff_dashboard_shows_weekly_active_user_count(staff_client):
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
def test_staff_dashboard_shows_weekly_event_count(staff_client):
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
def test_staff_dashboard_shows_zero_state_when_no_analytics_events(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "주간 활성 사용자" in content
    assert "주간 이벤트 기록" in content
    assert "0명" in content
    assert "0건" in content
