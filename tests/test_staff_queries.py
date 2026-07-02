"""staff/queries.py::recent_staff_actions — PR-2 sub-step F (backend)."""
import pytest

from drafts.models import EventDraft
from staff.models import StaffActionLog
from staff.queries import recent_staff_actions


@pytest.mark.django_db
def test_recent_staff_actions_orders_newest_first(make_user):
    actor = make_user(is_staff=True)
    first = StaffActionLog.objects.create(actor=actor, action="approve")
    second = StaffActionLog.objects.create(actor=actor, action="reject")

    result = recent_staff_actions()

    assert result == [second, first]


@pytest.mark.django_db
def test_recent_staff_actions_respects_limit(make_user):
    actor = make_user(is_staff=True)
    for _ in range(5):
        StaffActionLog.objects.create(actor=actor, action="approve")

    result = recent_staff_actions(limit=2)

    assert len(result) == 2


@pytest.mark.django_db
def test_recent_staff_actions_returns_empty_list_when_none():
    result = recent_staff_actions()

    assert result == []


@pytest.mark.django_db
def test_recent_staff_actions_exposes_actor_and_target_draft_without_error(make_user):
    actor = make_user(is_staff=True)
    draft = EventDraft.objects.create(
        source_url="https://example.com/recent-action-draft",
        extracted_title="드래프트 최근",
    )
    StaffActionLog.objects.create(
        actor=actor, action="approve", target_draft=draft
    )

    result = recent_staff_actions()

    assert result[0].actor.email == actor.email
    assert result[0].target_draft.extracted_title == "드래프트 최근"
