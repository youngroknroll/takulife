"""core.models.AnalyticsEvent (PR-0e checkpoint B1).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest
from django.core.exceptions import ValidationError

from core.models import AnalyticsEvent


ALLOWED_EVENT_NAMES = [
    "event_list_viewed",
    "event_searched",
    "event_detail_viewed",
    "event_interested",
    "event_planned",
    "event_marked_visited",
    "visit_record_created",
    "visit_photo_added",
]


@pytest.mark.django_db
@pytest.mark.parametrize("event_name", ALLOWED_EVENT_NAMES)
def test_analytics_event_accepts_every_allowed_event_name(event_name):
    event = AnalyticsEvent(event_name=event_name, user_key="abc123")

    event.full_clean()


@pytest.mark.django_db
def test_analytics_event_rejects_unknown_event_name():
    event = AnalyticsEvent(event_name="not_a_real_event", user_key="abc123")

    with pytest.raises(ValidationError):
        event.full_clean()
