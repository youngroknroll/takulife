"""core.analytics.record_event resilience and privacy guards
(PR-0e checkpoints B8, B9).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest

from core.analytics import record_event
from core.models import AnalyticsEvent


@pytest.mark.domain
@pytest.mark.django_db
def test_분석_이벤트_저장이_실패해도_예외를_전파하지_않는다(monkeypatch, make_user, caplog):
    user = make_user()

    def _boom(**kwargs):
        raise RuntimeError("simulated persistence outage")

    monkeypatch.setattr(AnalyticsEvent.objects, "create", _boom)

    # Must not raise — the calling domain action (e.g. creating a visit
    # record) must succeed even if analytics persistence is broken.
    record_event(AnalyticsEvent.EventName.EVENT_LIST_VIEWED, user=user)

    assert AnalyticsEvent.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "forbidden_key",
    ["short_review", "note", "email", "photo_url", "image", "name", "memo"],
    ids=["한줄_후기", "비고_note", "이메일", "사진_URL", "이미지_파일", "이름", "메모"],
)
def test_금지된_컨텍스트_키가_있으면_분석_이벤트_기록이_예외로_실패한다(make_user, forbidden_key):
    user = make_user()

    with pytest.raises(ValueError):
        record_event(
            AnalyticsEvent.EventName.VISIT_RECORD_CREATED,
            user=user,
            context={forbidden_key: "should never be stored"},
        )

    assert AnalyticsEvent.objects.count() == 0
