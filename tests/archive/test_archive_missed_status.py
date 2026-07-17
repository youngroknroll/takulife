"""Behavior tests for the hybrid 'missed' (놓침) archive status.

Auto-derived: a planned event whose end_date has passed, un-visited, not opted
out, is shown as 'missed' at read time without mutating the stored row.
Manual override: stored visited/missed win; revert_to_planned pins planned.

Design: .docs/plans/2026-06-26-archive-missed-status-design.md
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
    e = _event(date(2026, 6, 20))  # ended before today
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
    """end_date == today means still ongoing → not missed (strict <)."""
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
    """Manually marking missed works even before the event ends."""
    user = make_user(username="d8")
    e = _event(date(2026, 6, 30))  # future
    s = make_status(user, event=e, status="missed")
    assert _derived(s) == "missed"


# ---------------------------------------------------------------------------
# Read layer routes through the derivation (counts + filter)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_상태별_집계를_조회하면_지난_계획_상태가_놓침_집계로_이동한다(make_user, make_status):
    user = make_user(username="c1")
    make_status(user, event=_event(date(2026, 6, 20), title="past"), status="planned")
    make_status(user, event=_event(date(2026, 6, 30), title="future"), status="planned")

    counts = user_status_counts(user, today=TODAY)

    assert counts["planned"] == 1  # only the future one
    assert counts["missed"] == 1  # auto-missed past one
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
# Manual override services
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_자동_놓침_상태를_계획으로_되돌리면_missed_overridden이_설정되어_다시_놓침으로_돌아가지_않는다(make_user, make_status):
    """Reverting an auto-missed row stays planned — no oscillation back to missed."""
    user = make_user(username="s1")
    e = _event(date(2026, 6, 20))  # past
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
    e = _event(date(2026, 6, 30))  # future
    s = make_status(user, event=e, status="planned")

    mark_missed(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "missed"
    assert _derived(s) == "missed"


@pytest.mark.django_db
def test_자동_놓침_상태를_방문완료로_처리하면_놓침에서_제외되고_방문완료로_파생된다(make_user, make_status):
    user = make_user(username="s3")
    e = _event(date(2026, 6, 20))  # past, would be auto-missed
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "missed"

    mark_visited(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "visited"
    assert _derived(s) == "visited"


# ---------------------------------------------------------------------------
# Derived status against the real "today" (mirrors the PATCH revert-to-planned
# HTTP flow in test_user_event_status_api.py's
# test_patch_to_planned_pins_override_so_it_stays_planned)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_실제_오늘_날짜_기준으로도_missed_overridden된_지난_계획_상태는_계획으로_파생된다(
    make_user, make_status
):
    """A status dated firmly in the past (2020) with missed_overridden=True
    derives as 'planned' against the actual current date, not the module's
    simulated TODAY — the same scenario the PATCH revert-to-planned endpoint
    persists, reconstructed here directly via ORM."""
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
