"""하이브리드 '놓침' 아카이브 상태에 대한 동작 테스트.

자동 파생: end_date가 지났고 방문 기록도 옵트아웃도 없는 계획 상태는, 저장된
행을 바꾸지 않고 조회 시점에 '놓침'으로 표시된다. 수동 오버라이드: 저장된
방문완료/놓침 상태가 우선하며 revert_to_planned는 계획 상태로 고정한다.

설계 문서: .docs/plans/2026-06-26-archive-missed-status-design.md
"""
from datetime import date

import pytest

from archive.models import UserEventStatus
from archive.queries import list_user_statuses, user_status_counts
from archive.services import mark_missed, mark_visited, revert_to_planned
from events.models import Event

TODAY = date(2026, 6, 26)

pytestmark = pytest.mark.domain


def _event(end_date, *, title="E", start_date=date(2026, 6, 1)):
    return Event.objects.create(
        title=title,
        publish_status=Event.PublishStatus.PUBLISHED,
        start_date=start_date,
        end_date=end_date,
    )


def _derived(status_row):
    return (
        UserEventStatus.objects.filter(pk=status_row.pk)
        .with_derived_status(today=TODAY)
        .first()
        .derived_status
    )


@pytest.mark.django_db
def test_종료일이_지난_계획_상태를_방문_기록_없이_조회하면_놓침으로_파생된다(make_user, make_status):
    user = make_user(username="d1")
    e = _event(date(2026, 6, 20))  # 오늘보다 앞서 종료됨
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "missed"


@pytest.mark.django_db
def test_종료일이_지난_계획_상태라도_방문_기록이_있으면_놓침으로_파생되지_않는다(make_user, make_status, make_visit):
    user = make_user(username="d2")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="planned")
    make_visit(user, event=e, visited_on=date(2026, 6, 19))
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_종료일이_지난_계획_상태라도_missed_overridden이면_계획으로_파생된다(make_user, make_status):
    user = make_user(username="d3")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="planned", missed_overridden=True)
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_종료일이_아직_남은_계획_상태는_계획으로_파생된다(make_user, make_status):
    user = make_user(username="d4")
    e = _event(date(2026, 6, 30))
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_종료일이_오늘인_계획_상태는_아직_진행중으로_보아_놓침으로_파생되지_않는다(make_user, make_status):
    """end_date == today는 아직 진행 중으로 보아 놓침이 아니다(< 비교이므로)."""
    user = make_user(username="d5")
    e = _event(TODAY)
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_종료일이_없는_계획_상태는_계획으로_파생된다(make_user, make_status):
    user = make_user(username="d6")
    e = _event(None)
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_저장된_방문완료_상태는_종료일이_지나도_놓침으로_파생되지_않는다(make_user, make_status):
    user = make_user(username="d7")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="visited")
    assert _derived(s) == "visited"


@pytest.mark.django_db
def test_행사_종료_전이라도_수동으로_놓침_처리한_상태는_놓침으로_파생된다(make_user, make_status):
    """행사가 끝나기 전이라도 수동으로 놓침 처리할 수 있다."""
    user = make_user(username="d8")
    e = _event(date(2026, 6, 30))  # 미래
    s = make_status(user, event=e, status="missed")
    assert _derived(s) == "missed"


# ---------------------------------------------------------------------------
# 읽기 계층은 파생 로직을 거친다(집계 + 필터)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_상태별_집계를_조회하면_지난_계획_상태가_놓침_집계로_이동한다(make_user, make_status):
    user = make_user(username="c1")
    make_status(user, event=_event(date(2026, 6, 20), title="past"), status="planned")
    make_status(user, event=_event(date(2026, 6, 30), title="future"), status="planned")

    counts = user_status_counts(user, today=TODAY)

    assert counts["planned"] == 1  # 미래 항목 하나만
    assert counts["missed"] == 1  # 자동 놓침 처리된 과거 항목
    assert counts["visited"] == 0


@pytest.mark.django_db
def test_놓침_필터로_목록을_조회하면_자동_놓침_항목이_포함되고_계획_필터에서는_제외된다(make_user, make_status):
    user = make_user(username="c2")
    past = make_status(user, event=_event(date(2026, 6, 20), title="past"), status="planned")
    future = make_status(user, event=_event(date(2026, 6, 30), title="future"), status="planned")

    missed = list(list_user_statuses(user, "missed", today=TODAY))
    planned = list(list_user_statuses(user, "planned", today=TODAY))

    assert [r.pk for r in missed] == [past.pk]
    assert [r.pk for r in planned] == [future.pk]


# ---------------------------------------------------------------------------
# 수동 오버라이드 서비스
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_자동_놓침_상태를_계획으로_되돌리면_missed_overridden이_설정되어_다시_놓침으로_돌아가지_않는다(make_user, make_status):
    """자동 놓침 행을 되돌리면 계획 상태를 유지하며 다시 놓침으로 진동하지 않는다."""
    user = make_user(username="s1")
    e = _event(date(2026, 6, 20))  # 과거
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "missed"

    revert_to_planned(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "planned"
    assert s.missed_overridden is True
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_행사_종료_전에_수동으로_놓침_처리하면_저장된_상태와_파생_상태가_모두_놓침이_된다(make_user, make_status):
    user = make_user(username="s2")
    e = _event(date(2026, 6, 30))  # 미래
    s = make_status(user, event=e, status="planned")

    mark_missed(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "missed"
    assert _derived(s) == "missed"


@pytest.mark.django_db
def test_자동_놓침_상태를_방문완료로_처리하면_놓침에서_제외되고_방문완료로_파생된다(make_user, make_status):
    user = make_user(username="s3")
    e = _event(date(2026, 6, 20))  # 과거 — 자동 놓침 처리될 대상
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "missed"

    mark_visited(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "visited"
    assert _derived(s) == "visited"


# ---------------------------------------------------------------------------
# 실제 "오늘" 날짜 기준 파생 상태 (test_user_event_status_api.py의
# test_patch_to_planned_pins_override_so_it_stays_planned가 검증하는
# PATCH revert-to-planned HTTP 흐름을 그대로 반영)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_실제_오늘_날짜_기준으로도_missed_overridden된_지난_계획_상태는_계획으로_파생된다(
    make_user, make_status
):
    """확실히 과거(2020년)이고 missed_overridden=True인 상태는, 모듈이 시뮬레이션한
    TODAY가 아니라 실제 현재 날짜 기준으로도 '계획'으로 파생된다 — PATCH
    revert-to-planned 엔드포인트가 저장하는 것과 같은 시나리오를 ORM으로 직접 재현한다."""
    user = make_user(username="s4")
    e = _event(date(2020, 1, 2), title="Long-past event", start_date=date(2020, 1, 1))
    s = make_status(user, event=e, status="planned", missed_overridden=True)

    derived = (
        UserEventStatus.objects.filter(pk=s.pk)
        .with_derived_status(today=date.today())
        .first()
        .derived_status
    )

    assert derived == "planned"
