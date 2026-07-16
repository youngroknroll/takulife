"""core.analytics.record_event resilience and privacy guards
(PR-0e checkpoints B8, B9).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest

from core.analytics import record_event
from core.models import AnalyticsEvent


@pytest.mark.django_db
def test_record_event_does_not_raise_when_persistence_fails(monkeypatch, make_user, caplog):
    user = make_user()

    def _boom(**kwargs):
        raise RuntimeError("simulated persistence outage")

    monkeypatch.setattr(AnalyticsEvent.objects, "create", _boom)

    # Must not raise — the calling domain action (e.g. creating a visit
    # record) must succeed even if analytics persistence is broken.
    record_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user=user)

    assert AnalyticsEvent.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "forbidden_key", ["short_review", "note", "email", "photo_url", "image", "name", "memo"]
)
def test_record_event_hard_fails_on_forbidden_context_key(make_user, forbidden_key):
    user = make_user()

    with pytest.raises(ValueError):
        record_event(
            AnalyticsEvent.EventName.VISIT_RECORD_CREATED,
            user=user,
            context={forbidden_key: "should never be stored"},
        )

    assert AnalyticsEvent.objects.count() == 0
