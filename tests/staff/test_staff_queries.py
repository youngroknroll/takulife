"""staff/queries.py::recent_staff_actions — PR-2 sub-step F (backend)."""
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import pytest
from django.utils import timezone

from events.models import Event
from staff.models import StaffActionLog
from staff.queries import (
    recent_staff_actions,
    staff_actions_count_since,
)


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
def test_recent_staff_actions_exposes_actor_and_target_draft_without_error(make_user, make_draft):
    actor = make_user(is_staff=True)
    draft = make_draft("https://example.com/recent-action-draft", extracted_title="드래프트 최근")
    StaffActionLog.objects.create(
        actor=actor, action="approve", target_draft=draft
    )

    result = recent_staff_actions()

    assert result[0].actor.email == actor.email
    assert result[0].target_draft.extracted_title == "드래프트 최근"


@pytest.mark.django_db
def test_recent_staff_actions_selects_related_target_event(
    make_user, django_assert_num_queries
):
    """PR-D1 item 1: select_related must cover target_event too, so reading
    target_event off each row costs no extra query (N+1 guard)."""
    actor = make_user(is_staff=True)
    event = Event.objects.create(
        title="최근 이벤트", publish_status=Event.PublishStatus.PUBLISHED
    )
    StaffActionLog.objects.create(
        actor=actor, action=StaffActionLog.Action.EVENT_UPDATE, target_event=event
    )

    with django_assert_num_queries(1):
        result = recent_staff_actions()
        assert result[0].target_event.title == "최근 이벤트"


@pytest.mark.django_db
def test_staff_actions_count_since_returns_zero_when_no_logs():
    result = staff_actions_count_since(days=7)
    assert result == 0


@pytest.mark.django_db
def test_staff_actions_count_since_counts_logs_within_window(make_user):
    actor = make_user(is_staff=True)
    for _ in range(4):
        StaffActionLog.objects.create(actor=actor, action="approve")
    result = staff_actions_count_since(days=7)
    assert result == 4


@pytest.mark.django_db
def test_staff_actions_count_since_excludes_logs_older_than_window(make_user):
    actor = make_user(is_staff=True)
    log = StaffActionLog.objects.create(actor=actor, action="approve")
    StaffActionLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=8)
    )
    result = staff_actions_count_since(days=7)
    assert result == 0


@pytest.mark.django_db
def test_staff_actions_count_since_offset_shifts_window(make_user):
    """10일 전 로그는 직전 7일 창(offset=7)엔 포함되고 최근 7일 창(offset=0)엔 제외된다."""
    actor = make_user(is_staff=True)
    log = StaffActionLog.objects.create(actor=actor, action="approve")
    StaffActionLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=10)
    )
    assert staff_actions_count_since(days=7, offset=7) == 1
    assert staff_actions_count_since(days=7, offset=0) == 0

