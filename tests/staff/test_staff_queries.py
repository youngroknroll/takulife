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
    staff_actions_per_day,
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


@pytest.mark.django_db
def test_staff_actions_per_day_fills_empty_days_with_zero():
    result = staff_actions_per_day(days=14)
    assert [row["count"] for row in result] == [0] * 14


@pytest.mark.django_db
def test_staff_actions_per_day_returns_exactly_days_entries_ascending_ending_today():
    result = staff_actions_per_day(days=14)
    dates = [row["date"] for row in result]
    assert len(result) == 14
    assert dates == sorted(dates)
    assert dates[-1] == timezone.localdate()


@pytest.mark.django_db
def test_staff_actions_per_day_sums_multiple_logs_on_same_day(make_user):
    actor = make_user(is_staff=True)
    for _ in range(3):
        StaffActionLog.objects.create(actor=actor, action="approve")
    result = staff_actions_per_day(days=14)
    today_row = result[-1]
    assert today_row["date"] == timezone.localdate()
    assert today_row["count"] == 3


@pytest.mark.django_db
def test_staff_actions_per_day_excludes_logs_outside_window(make_user):
    actor = make_user(is_staff=True)
    log = StaffActionLog.objects.create(actor=actor, action="approve")
    StaffActionLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=15)
    )
    result = staff_actions_per_day(days=14)
    assert sum(row["count"] for row in result) == 0


@pytest.mark.django_db
def test_staff_actions_per_day_buckets_by_kst_calendar_day_not_utc(make_user):
    """UTC 15:30에 기록된 로그는 KST로는 다음날 00:30 — KST 익일 버킷에 집계돼야 한다
    (UTC 날짜 그대로 버킷팅하면 하루 밀린 잘못된 결과가 나온다)."""
    actor = make_user(is_staff=True)
    log = StaffActionLog.objects.create(actor=actor, action="approve")
    today = timezone.localdate()
    utc_source_day = today - timedelta(days=2)
    backdated_utc = datetime(
        utc_source_day.year, utc_source_day.month, utc_source_day.day,
        15, 30, tzinfo=dt_timezone.utc,
    )
    StaffActionLog.objects.filter(pk=log.pk).update(created_at=backdated_utc)
    result = staff_actions_per_day(days=14)
    by_date = {row["date"]: row["count"] for row in result}
    assert by_date[today - timedelta(days=1)] == 1
    assert by_date[today - timedelta(days=2)] == 0
