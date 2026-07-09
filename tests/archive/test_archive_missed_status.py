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
def test_planned_past_unvisited_is_auto_missed(make_user, make_status):
    user = make_user(username="d1")
    e = _event(date(2026, 6, 20))  # ended before today
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "missed"


@pytest.mark.django_db
def test_planned_past_with_visit_is_not_missed(make_user, make_status, make_visit):
    user = make_user(username="d2")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="planned")
    make_visit(user, event=e, visited_on=date(2026, 6, 19))
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_planned_past_overridden_stays_planned(make_user, make_status):
    user = make_user(username="d3")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="planned", missed_overridden=True)
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_planned_future_is_planned(make_user, make_status):
    user = make_user(username="d4")
    e = _event(date(2026, 6, 30))
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_planned_boundary_today_is_not_missed(make_user, make_status):
    """end_date == today means still ongoing → not missed (strict <)."""
    user = make_user(username="d5")
    e = _event(TODAY)
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_planned_null_end_date_is_planned(make_user, make_status):
    user = make_user(username="d6")
    e = _event(None)
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_stored_visited_never_missed(make_user, make_status):
    user = make_user(username="d7")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="visited")
    assert _derived(s) == "visited"


@pytest.mark.django_db
def test_stored_missed_before_date_is_missed(make_user, make_status):
    """Manually marking missed works even before the event ends."""
    user = make_user(username="d8")
    e = _event(date(2026, 6, 30))  # future
    s = make_status(user, event=e, status="missed")
    assert _derived(s) == "missed"


# ---------------------------------------------------------------------------
# Read layer routes through the derivation (counts + filter)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_counts_move_past_planned_into_missed(make_user, make_status):
    user = make_user(username="c1")
    make_status(user, event=_event(date(2026, 6, 20), title="past"), status="planned")
    make_status(user, event=_event(date(2026, 6, 30), title="future"), status="planned")

    counts = user_status_counts(user, today=TODAY)

    assert counts["planned"] == 1  # only the future one
    assert counts["missed"] == 1  # auto-missed past one
    assert counts["visited"] == 0


@pytest.mark.django_db
def test_filter_missed_includes_auto_and_planned_excludes_it(make_user, make_status):
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
def test_revert_to_planned_pins_via_override(make_user, make_status):
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
def test_mark_missed_before_date(make_user, make_status):
    user = make_user(username="s2")
    e = _event(date(2026, 6, 30))  # future
    s = make_status(user, event=e, status="planned")

    mark_missed(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "missed"
    assert _derived(s) == "missed"


@pytest.mark.django_db
def test_mark_visited_removes_from_missed(make_user, make_status):
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
def test_planned_firmly_past_with_override_derives_planned_against_real_today(
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
