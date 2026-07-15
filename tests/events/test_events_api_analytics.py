"""Public events API analytics event recording
(PR-0e checkpoints B10, B11).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest

from core.models import AnalyticsEvent
from events.models import Event


@pytest.mark.django_db
def test_event_list_without_q_records_event_list_viewed(client, make_event):
    make_event(publish_status=Event.PublishStatus.PUBLISHED)

    client.get("/api/events/")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_SEARCHED
    ).count() == 0


@pytest.mark.django_db
def test_event_list_with_q_records_event_searched_not_viewed(client, make_event):
    make_event(title="Seoul popup event", publish_status=Event.PublishStatus.PUBLISHED)

    client.get("/api/events/", {"q": "popup"})

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_SEARCHED
    ).count() == 1
    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED
    ).count() == 0


@pytest.mark.django_db
def test_event_detail_success_records_event_detail_viewed(client, make_event):
    event = make_event(publish_status=Event.PublishStatus.PUBLISHED)

    client.get(f"/api/events/{event.id}/")

    events = AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_DETAIL_VIEWED
    )
    assert events.count() == 1
    assert events.get().target_id == event.id


@pytest.mark.django_db
def test_event_detail_404_does_not_record_event_detail_viewed(client, make_event):
    event = make_event(publish_status=Event.PublishStatus.DRAFT)

    client.get(f"/api/events/{event.id}/")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_DETAIL_VIEWED
    ).count() == 0
