"""아카이브 읽기 계층(archive/queries.py) 단위 테스트 — 예정 행사 조회.

list_user_planned_events/list_user_upcoming_planned_events를 검증한다.
"""

from datetime import date, timedelta

import pytest

from archive.queries import list_user_planned_events, list_user_upcoming_planned_events

TODAY = date(2026, 6, 26)

pytestmark = pytest.mark.domain


# ---------------------------------------------------------------------------
# list_user_planned_events (방문 기록 추가 시 선택 가능한 행사 집합)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문예정_행사_목록은_본인이_예정_등록한_게시된_행사만_반환한다(make_user, make_event, make_draft_event, make_status):
    user = make_user(username="planner")
    other = make_user(username="planner-other")
    planned = make_event(title="Planned")
    visited = make_event(title="Visited")
    missed = make_event(title="Missed")
    others_planned = make_event(title="Others planned")
    draft_planned = make_draft_event(title="Draft planned")

    make_status(user, event=planned, status="planned")
    make_status(user, event=visited, status="visited")
    make_status(user, event=missed, status="missed")
    make_status(user, event=draft_planned, status="planned")
    make_status(other, event=others_planned, status="planned")

    events = list(list_user_planned_events(user))

    assert planned in events
    assert visited not in events
    assert missed not in events
    assert others_planned not in events
    assert draft_planned not in events


# ---------------------------------------------------------------------------
# list_user_upcoming_planned_events (collection-first home: 다가오는 예정 행사)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_다가오는_예정_행사_목록은_본인이_예정_등록한_게시된_행사로_범위를_좁힌다(
    make_user, make_event, make_draft_event, make_status
):
    user = make_user(username="upcoming-planner")
    other = make_user(username="upcoming-planner-other")
    future = TODAY + timedelta(days=5)
    planned = make_event(title="Planned", start_date=future)
    visited = make_event(title="Visited", start_date=future)
    missed = make_event(title="Missed", start_date=future)
    others_planned = make_event(title="Others planned", start_date=future)
    draft_planned = make_draft_event(title="Draft planned", start_date=future)

    make_status(user, event=planned, status="planned")
    make_status(user, event=visited, status="visited")
    make_status(user, event=missed, status="missed")
    make_status(user, event=draft_planned, status="planned")
    make_status(other, event=others_planned, status="planned")

    events = list(list_user_upcoming_planned_events(user, today=TODAY))

    assert planned in events
    assert visited not in events
    assert missed not in events
    assert others_planned not in events
    assert draft_planned not in events


@pytest.mark.django_db
def test_다가오는_예정_행사_목록은_오늘과_지난_시작일을_제외하고_내일_이후만_포함한다(
    make_user, make_event, make_status
):
    user = make_user(username="upcoming-boundary")
    yesterday_event = make_event(title="Yesterday", start_date=TODAY - timedelta(days=1))
    today_event = make_event(title="Today", start_date=TODAY)
    tomorrow_event = make_event(title="Tomorrow", start_date=TODAY + timedelta(days=1))

    make_status(user, event=yesterday_event, status="planned")
    make_status(user, event=today_event, status="planned")
    make_status(user, event=tomorrow_event, status="planned")

    events = list(list_user_upcoming_planned_events(user, today=TODAY))

    assert yesterday_event not in events
    assert today_event not in events  # 오늘은 제외됨(gt이지 gte가 아님)
    assert tomorrow_event in events


@pytest.mark.django_db
def test_다가오는_예정_행사_목록은_시작일이_이른_순으로_정렬된다(
    make_user, make_event, make_status
):
    user = make_user(username="upcoming-order")
    third = make_event(title="Third", start_date=TODAY + timedelta(days=30))
    first = make_event(title="First", start_date=TODAY + timedelta(days=1))
    second = make_event(title="Second", start_date=TODAY + timedelta(days=10))

    make_status(user, event=third, status="planned")
    make_status(user, event=first, status="planned")
    make_status(user, event=second, status="planned")

    titles = [e.title for e in list_user_upcoming_planned_events(user, today=TODAY)]

    assert titles == ["First", "Second", "Third"]
