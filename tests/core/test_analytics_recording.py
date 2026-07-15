"""core.analytics.record_event (PR-0e checkpoint B4).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest

from core.analytics import pseudonymous_user_key, record_event
from core.models import AnalyticsEvent


@pytest.mark.django_db
def test_record_event_persists_one_row_with_pseudonymous_user_key(make_user):
    user = make_user()

    record_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user=user)

    assert AnalyticsEvent.objects.count() == 1
    event = AnalyticsEvent.objects.get()
    assert event.event_name == AnalyticsEvent.EventName.EVENT_LIST_VIEWED
    assert event.user_key == pseudonymous_user_key(user)
