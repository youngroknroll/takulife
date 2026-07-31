"""공개 행사 API의 분석 이벤트 기록을 검증한다."""
import pytest

from core.models import AnalyticsEvent
from events.models import Event

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_검색어_없이_행사_목록을_조회하면_목록_조회_이벤트가_기록된다(client, make_event):
    make_event(publish_status=Event.PublishStatus.PUBLISHED)

    client.get("/api/events/")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_SEARCHED
    ).count() == 0


@pytest.mark.django_db
def test_검색어로_행사_목록을_조회하면_검색_이벤트만_기록되고_목록_조회_이벤트는_기록되지_않는다(client, make_event):
    make_event(title="Seoul popup event", publish_status=Event.PublishStatus.PUBLISHED)

    client.get("/api/events/", {"q": "popup"})

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_SEARCHED
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED
    ).count() == 0


@pytest.mark.django_db
def test_행사_상세를_조회하면_상세_조회_이벤트가_기록된다(client, make_event):
    event = make_event(publish_status=Event.PublishStatus.PUBLISHED)

    client.get(f"/api/events/{event.id}/")

    events = AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_DETAIL_VIEWED
    )
    assert events.count() == 1
    assert events.get().target_id == event.id


@pytest.mark.django_db
def test_비공개_행사_상세_조회는_404이며_상세_조회_이벤트가_기록되지_않는다(client, make_event):
    event = make_event(publish_status=Event.PublishStatus.DRAFT)

    client.get(f"/api/events/{event.id}/")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_DETAIL_VIEWED
    ).count() == 0
