"""Unit tests for the archive read layer (archive/queries.py)."""

import pytest

from archive.models import EventInterest, UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_STATUS_SLUGS,
    list_user_interests,
    list_user_planned_events,
    list_user_statuses,
    list_user_visit_records,
    user_interest_count,
    user_interest_event_ids,
    user_status_counts,
)


@pytest.mark.django_db
def test_user_status_counts_zero_fills_all_slugs(make_user):
    """A user with no statuses gets every canonical slug present and zero."""
    user = make_user(username="counts-empty")

    counts = user_status_counts(user)

    assert set(counts) == set(ARCHIVE_STATUS_SLUGS)
    assert all(value == 0 for value in counts.values())


@pytest.mark.django_db
def test_user_status_counts_counts_per_status(make_user, make_event):
    """Counts reflect the user's rows and ignore other users' rows."""
    user = make_user(username="counts-user")
    other = make_user(username="counts-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    UserEventStatus.objects.create(user=user, event=e1, status="planned")
    UserEventStatus.objects.create(user=user, event=e2, status="visited")
    UserEventStatus.objects.create(user=other, event=e1, status="planned")

    counts = user_status_counts(user)

    assert counts["planned"] == 1
    assert counts["visited"] == 1
    assert counts["missed"] == 0


@pytest.mark.django_db
def test_list_user_statuses_filters_by_user_and_status(make_user, make_event):
    user = make_user(username="list-status-user")
    other = make_user(username="list-status-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    UserEventStatus.objects.create(user=user, event=e1, status="planned")
    UserEventStatus.objects.create(user=user, event=e2, status="visited")
    UserEventStatus.objects.create(user=other, event=e1, status="planned")

    assert list_user_statuses(user).count() == 2
    planned_only = list_user_statuses(user, "planned")
    assert planned_only.count() == 1
    assert planned_only.first().event_id == e1.id


@pytest.mark.django_db
def test_list_user_visit_records_scoped_and_ordered(make_user, make_event):
    user = make_user(username="list-visit-user")
    other = make_user(username="list-visit-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    older = VisitRecord.objects.create(user=user, event=e1, visited_on="2026-05-01")
    newer = VisitRecord.objects.create(user=user, event=e2, visited_on="2026-06-01")
    VisitRecord.objects.create(user=other, event=e1, visited_on="2026-06-15")

    rows = list(list_user_visit_records(user))

    assert [r.id for r in rows] == [newer.id, older.id]


# ---------------------------------------------------------------------------
# ARCHIVE_STATUS_SLUGS no longer contains "interested"
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_archive_status_slugs_excludes_interested(django_user_model):
    assert "interested" not in ARCHIVE_STATUS_SLUGS
    assert "planned" in ARCHIVE_STATUS_SLUGS
    assert "visited" in ARCHIVE_STATUS_SLUGS
    assert "missed" in ARCHIVE_STATUS_SLUGS


# ---------------------------------------------------------------------------
# user_status_counts — interested not counted even if row exists at DB level
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_status_counts_excludes_interested_key(make_user):
    """user_status_counts must not include 'interested' as a key."""
    user = make_user(username="counts-no-interested")
    counts = user_status_counts(user)
    assert "interested" not in counts


# ---------------------------------------------------------------------------
# list_user_interests — scoped to user, select_related event, newest-first
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_user_interests_scoped_and_ordered(make_user, make_event):
    user = make_user(username="interest-query-user")
    other = make_user(username="interest-query-other")
    e1 = make_event(title="Interest E1")
    e2 = make_event(title="Interest E2")
    e3 = make_event(title="Interest E3")

    first = EventInterest.objects.create(user=user, event=e1)
    second = EventInterest.objects.create(user=user, event=e2)
    EventInterest.objects.create(user=other, event=e3)

    rows = list(list_user_interests(user))

    assert len(rows) == 2
    assert rows[0].pk == second.pk
    assert rows[1].pk == first.pk
    assert rows[0].event.id == e2.id


# ---------------------------------------------------------------------------
# user_interest_event_ids — returns {event_id: interest_id} bounded by ids
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_interest_event_ids_bounded(make_user, make_event):
    user = make_user(username="interest-ids-user")
    other = make_user(username="interest-ids-other")
    e1 = make_event(title="Interest IDs E1")
    e2 = make_event(title="Interest IDs E2")
    e3 = make_event(title="Interest IDs E3")

    i1 = EventInterest.objects.create(user=user, event=e1)
    EventInterest.objects.create(user=user, event=e2)
    EventInterest.objects.create(user=other, event=e3)

    result = user_interest_event_ids(user, event_ids=[e1.id, e3.id])

    assert result == {e1.id: i1.pk}


@pytest.mark.django_db
def test_user_interest_event_ids_unbounded(make_user, make_event):
    user = make_user(username="interest-ids-unbound-user")
    e1 = make_event(title="Interest Unbound E1")
    e2 = make_event(title="Interest Unbound E2")

    i1 = EventInterest.objects.create(user=user, event=e1)
    i2 = EventInterest.objects.create(user=user, event=e2)

    result = user_interest_event_ids(user)

    assert result == {e1.id: i1.pk, e2.id: i2.pk}


# ---------------------------------------------------------------------------
# user_interest_count
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_interest_count(make_user, make_event):
    user = make_user(username="interest-count-user")
    other = make_user(username="interest-count-other")
    e1 = make_event(title="Interest Count E1")
    e2 = make_event(title="Interest Count E2")
    e3 = make_event(title="Interest Count E3")

    EventInterest.objects.create(user=user, event=e1)
    EventInterest.objects.create(user=user, event=e2)
    EventInterest.objects.create(user=other, event=e3)

    assert user_interest_count(user) == 2


# ---------------------------------------------------------------------------
# list_user_planned_events (selectable set when adding a visit record)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_user_planned_events_returns_only_user_planned_published(
    make_user, make_event, make_draft_event
):
    user = make_user(username="planner")
    other = make_user(username="planner-other")
    planned = make_event(title="Planned")
    visited = make_event(title="Visited")
    missed = make_event(title="Missed")
    others_planned = make_event(title="Others planned")
    draft_planned = make_draft_event(title="Draft planned")

    UserEventStatus.objects.create(user=user, event=planned, status="planned")
    UserEventStatus.objects.create(user=user, event=visited, status="visited")
    UserEventStatus.objects.create(user=user, event=missed, status="missed")
    UserEventStatus.objects.create(user=user, event=draft_planned, status="planned")
    UserEventStatus.objects.create(user=other, event=others_planned, status="planned")

    events = list(list_user_planned_events(user))

    assert planned in events
    assert visited not in events  # different status
    assert missed not in events  # different status
    assert others_planned not in events  # different user
    assert draft_planned not in events  # not published
