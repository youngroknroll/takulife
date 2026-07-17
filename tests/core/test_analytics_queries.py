"""core.analytics aggregate read queries (PR-0e checkpoint B13).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import datetime

import pytest
from django.utils import timezone

from core.analytics import distinct_user_key_count_since, event_name_counts_since
from core.models import AnalyticsEvent

pytestmark = pytest.mark.domain


def _create_event(event_name, user_key, days_ago=0):
    event = AnalyticsEvent.objects.create(event_name=event_name, user_key=user_key)
    if days_ago:
        AnalyticsEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=days_ago)
        )
    return event


@pytest.mark.django_db
def test_최근_N일_창_안에서_고유_사용자_키_수를_센다():
    _create_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, "user-a")
    _create_event(AnalyticsEvent.EventName.EVENT_SEARCHED, "user-a")
    _create_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, "user-b")
    _create_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, "user-c", days_ago=10)

    assert distinct_user_key_count_since(days=7) == 2


@pytest.mark.django_db
def test_빈_사용자_키는_고유_사용자_수_집계에서_제외된다():
    _create_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, "")
    _create_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, "user-a")

    assert distinct_user_key_count_since(days=7) == 1


@pytest.mark.django_db
def test_최근_N일_창_안에서_이벤트명별_발생_건수를_센다():
    _create_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, "user-a")
    _create_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, "user-b")
    _create_event(AnalyticsEvent.EventName.EVENT_SEARCHED, "user-a")
    _create_event(AnalyticsEvent.EventName.EVENT_SEARCHED, "user-a", days_ago=10)

    counts = event_name_counts_since(days=7)

    assert counts[AnalyticsEvent.EventName.EVENT_LIST_VIEWED] == 2
    assert counts[AnalyticsEvent.EventName.EVENT_SEARCHED] == 1
