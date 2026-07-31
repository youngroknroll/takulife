"""core.analytics.record_event 검증
(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8).
"""
import pytest

from core.analytics import pseudonymous_user_key, record_event
from core.models import AnalyticsEvent

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_분석_이벤트를_기록하면_의사식별자_키를_가진_행_하나가_저장된다(make_user):
    user = make_user()

    record_event(event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user=user)

    assert AnalyticsEvent.objects.count() == 1
    event = AnalyticsEvent.objects.get()
    assert event.event_name == AnalyticsEvent.EventName.EVENT_LIST_VIEWED
    assert event.user_key == pseudonymous_user_key(user=user)
