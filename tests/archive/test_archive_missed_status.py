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


def _user(django_user_model, username):
    return django_user_model.objects.create_user(
        email=f"{username}@example.com", username=username, password="pw-12345678"
    )


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
def test_planned_past_unvisited_is_auto_missed(django_user_model, make_status):
    user = _user(django_user_model, "d1")
    e = _event(date(2026, 6, 20))  # ended before today
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "missed"


@pytest.mark.django_db
def test_planned_past_with_visit_is_not_missed(django_user_model, make_status, make_visit):
    user = _user(django_user_model, "d2")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="planned")
    make_visit(user, event=e, visited_on=date(2026, 6, 19))
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_planned_past_overridden_stays_planned(django_user_model, make_status):
    user = _user(django_user_model, "d3")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="planned", missed_overridden=True)
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_planned_future_is_planned(django_user_model, make_status):
    user = _user(django_user_model, "d4")
    e = _event(date(2026, 6, 30))
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_planned_boundary_today_is_not_missed(django_user_model, make_status):
    """end_date == today means still ongoing → not missed (strict <)."""
    user = _user(django_user_model, "d5")
    e = _event(TODAY)
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_planned_null_end_date_is_planned(django_user_model, make_status):
    user = _user(django_user_model, "d6")
    e = _event(None)
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_stored_visited_never_missed(django_user_model, make_status):
    user = _user(django_user_model, "d7")
    e = _event(date(2026, 6, 20))
    s = make_status(user, event=e, status="visited")
    assert _derived(s) == "visited"


@pytest.mark.django_db
def test_stored_missed_before_date_is_missed(django_user_model, make_status):
    """Manually marking missed works even before the event ends."""
    user = _user(django_user_model, "d8")
    e = _event(date(2026, 6, 30))  # future
    s = make_status(user, event=e, status="missed")
    assert _derived(s) == "missed"


# ---------------------------------------------------------------------------
# Read layer routes through the derivation (counts + filter)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_counts_move_past_planned_into_missed(django_user_model, make_status):
    user = _user(django_user_model, "c1")
    make_status(user, event=_event(date(2026, 6, 20), title="past"), status="planned")
    make_status(user, event=_event(date(2026, 6, 30), title="future"), status="planned")

    counts = user_status_counts(user, today=TODAY)

    assert counts["planned"] == 1  # only the future one
    assert counts["missed"] == 1  # auto-missed past one
    assert counts["visited"] == 0


@pytest.mark.django_db
def test_filter_missed_includes_auto_and_planned_excludes_it(django_user_model, make_status):
    user = _user(django_user_model, "c2")
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
def test_revert_to_planned_pins_via_override(django_user_model, make_status):
    """Reverting an auto-missed row stays planned — no oscillation back to missed."""
    user = _user(django_user_model, "s1")
    e = _event(date(2026, 6, 20))  # past
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "missed"

    revert_to_planned(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "planned"
    assert s.missed_overridden is True
    assert _derived(s) == "planned"


@pytest.mark.django_db
def test_mark_missed_before_date(django_user_model, make_status):
    user = _user(django_user_model, "s2")
    e = _event(date(2026, 6, 30))  # future
    s = make_status(user, event=e, status="planned")

    mark_missed(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "missed"
    assert _derived(s) == "missed"


@pytest.mark.django_db
def test_mark_visited_removes_from_missed(django_user_model, make_status):
    user = _user(django_user_model, "s3")
    e = _event(date(2026, 6, 20))  # past, would be auto-missed
    s = make_status(user, event=e, status="planned")
    assert _derived(s) == "missed"

    mark_visited(user_event_status=s)
    s.refresh_from_db()

    assert s.status == "visited"
    assert _derived(s) == "visited"
