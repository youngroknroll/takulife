"""staff/queries.py::recent_staff_actions 등 스태프 액션 조회·집계 쿼리 검증."""
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


@pytest.mark.domain
@pytest.mark.django_db
def test_최근_스태프_액션_목록은_최신순으로_정렬된다(make_user):
    actor = make_user(is_staff=True)
    first = StaffActionLog.objects.create(actor=actor, action="approve")
    second = StaffActionLog.objects.create(actor=actor, action="reject")

    result = recent_staff_actions()

    assert result == [second, first]


@pytest.mark.domain
@pytest.mark.django_db
def test_최근_스태프_액션_조회시_limit을_지정하면_해당_건수만큼만_반환된다(make_user):
    actor = make_user(is_staff=True)
    for _ in range(5):
        StaffActionLog.objects.create(actor=actor, action="approve")

    result = recent_staff_actions(limit=2)

    assert len(result) == 2


@pytest.mark.domain
@pytest.mark.django_db
def test_스태프_액션_로그가_없으면_최근_액션_조회는_빈_목록을_반환한다():
    result = recent_staff_actions()

    assert result == []


@pytest.mark.domain
@pytest.mark.django_db
def test_최근_스태프_액션은_행위자와_대상_드래프트_정보를_오류_없이_함께_노출한다(make_user, make_draft):
    actor = make_user(is_staff=True)
    draft = make_draft("https://example.com/recent-action-draft", extracted_title="드래프트 최근")
    StaffActionLog.objects.create(
        actor=actor, action="approve", target_draft=draft
    )

    result = recent_staff_actions()

    assert result[0].actor.email == actor.email
    assert result[0].target_draft.extracted_title == "드래프트 최근"


@pytest.mark.contract
@pytest.mark.django_db
def test_최근_스태프_액션_조회는_대상_이벤트를_추가_쿼리_없이_함께_가져온다(
    make_user, django_assert_num_queries
):
    """select_related가 target_event까지 포함해야 N+1 쿼리가 발생하지 않는다."""
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


@pytest.mark.domain
@pytest.mark.django_db
def test_스태프_액션_로그가_없으면_기간_내_건수_집계는_0이다():
    result = staff_actions_count_since(days=7)
    assert result == 0


@pytest.mark.domain
@pytest.mark.django_db
def test_지정한_기간_내의_스태프_액션_로그_건수를_정확히_집계한다(make_user):
    actor = make_user(is_staff=True)
    for _ in range(4):
        StaffActionLog.objects.create(actor=actor, action="approve")
    result = staff_actions_count_since(days=7)
    assert result == 4


@pytest.mark.domain
@pytest.mark.django_db
def test_지정한_기간보다_오래된_스태프_액션_로그는_집계에서_제외된다(make_user):
    actor = make_user(is_staff=True)
    log = StaffActionLog.objects.create(actor=actor, action="approve")
    StaffActionLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=8)
    )
    result = staff_actions_count_since(days=7)
    assert result == 0


@pytest.mark.domain
@pytest.mark.django_db
def test_offset을_지정하면_집계_기간이_그만큼_과거로_이동한다(make_user):
    """10일 전 로그는 직전 7일 창(offset=7)엔 포함되고 최근 7일 창(offset=0)엔 제외된다."""
    actor = make_user(is_staff=True)
    log = StaffActionLog.objects.create(actor=actor, action="approve")
    StaffActionLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=10)
    )
    assert staff_actions_count_since(days=7, offset=7) == 1
    assert staff_actions_count_since(days=7, offset=0) == 0


@pytest.mark.domain
@pytest.mark.django_db
def test_로그가_없는_날짜도_일별_집계에서_0건으로_채워진다():
    result = staff_actions_per_day(days=14)
    assert [row["count"] for row in result] == [0] * 14


@pytest.mark.domain
@pytest.mark.django_db
def test_일별_집계는_지정한_일수만큼_오늘로_끝나는_오름차순_날짜_목록을_반환한다():
    result = staff_actions_per_day(days=14)
    dates = [row["date"] for row in result]
    assert len(result) == 14
    assert dates == sorted(dates)
    assert dates[-1] == timezone.localdate()


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_날짜에_여러_로그가_있으면_일별_집계에서_합산된다(make_user):
    actor = make_user(is_staff=True)
    for _ in range(3):
        StaffActionLog.objects.create(actor=actor, action="approve")
    result = staff_actions_per_day(days=14)
    today_row = result[-1]
    assert today_row["date"] == timezone.localdate()
    assert today_row["count"] == 3


@pytest.mark.domain
@pytest.mark.django_db
def test_집계_기간_밖의_로그는_일별_집계에서_제외된다(make_user):
    actor = make_user(is_staff=True)
    log = StaffActionLog.objects.create(actor=actor, action="approve")
    StaffActionLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=15)
    )
    result = staff_actions_per_day(days=14)
    assert sum(row["count"] for row in result) == 0


@pytest.mark.domain
@pytest.mark.django_db
def test_일별_집계는_UTC가_아닌_KST_달력_날짜_기준으로_버킷팅된다(make_user):
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
