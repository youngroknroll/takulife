"""Unit tests for the archive read layer (archive/queries.py)."""

import pytest

from archive.models import EventInterest, UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_STATUS_SLUGS,
    list_user_interests,
    list_user_statuses,
    list_user_visit_records,
    user_interest_count,
    user_interest_event_ids,
    user_status_counts,
)
from events.models import Event


def _make_user(django_user_model, username):
    return django_user_model.objects.create_user(username=username, password="pw-12345678")


def _make_published_event(title="Published Event"):
    return Event.objects.create(title=title, publish_status=Event.PublishStatus.PUBLISHED)


@pytest.mark.django_db
def test_user_status_counts_zero_fills_all_slugs(django_user_model):
    """A user with no statuses gets every canonical slug present and zero."""
    user = _make_user(django_user_model, "counts-empty")

    counts = user_status_counts(user)

    assert set(counts) == set(ARCHIVE_STATUS_SLUGS)
    assert all(value == 0 for value in counts.values())


@pytest.mark.django_db
def test_user_status_counts_counts_per_status(django_user_model):
    """Counts reflect the user's rows and ignore other users' rows."""
    user = _make_user(django_user_model, "counts-user")
    other = _make_user(django_user_model, "counts-other")
    e1 = _make_published_event("E1")
    e2 = _make_published_event("E2")

    UserEventStatus.objects.create(user=user, event=e1, status="planned")
    UserEventStatus.objects.create(user=user, event=e2, status="visited")
    UserEventStatus.objects.create(user=other, event=e1, status="planned")

    counts = user_status_counts(user)

    assert counts["planned"] == 1
    assert counts["visited"] == 1
    assert counts["missed"] == 0


@pytest.mark.django_db
def test_list_user_statuses_filters_by_user_and_status(django_user_model):
    user = _make_user(django_user_model, "list-status-user")
    other = _make_user(django_user_model, "list-status-other")
    e1 = _make_published_event("E1")
    e2 = _make_published_event("E2")

    UserEventStatus.objects.create(user=user, event=e1, status="planned")
    UserEventStatus.objects.create(user=user, event=e2, status="visited")
    UserEventStatus.objects.create(user=other, event=e1, status="planned")

    assert list_user_statuses(user).count() == 2
    planned_only = list_user_statuses(user, "planned")
    assert planned_only.count() == 1
    assert planned_only.first().event_id == e1.id


@pytest.mark.django_db
def test_list_user_visit_records_scoped_and_ordered(django_user_model):
    user = _make_user(django_user_model, "list-visit-user")
    other = _make_user(django_user_model, "list-visit-other")
    e1 = _make_published_event("E1")
    e2 = _make_published_event("E2")

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
def test_user_status_counts_excludes_interested_key(django_user_model):
    """user_status_counts must not include 'interested' as a key."""
    user = _make_user(django_user_model, "counts-no-interested")
    counts = user_status_counts(user)
    assert "interested" not in counts


# ---------------------------------------------------------------------------
# list_user_interests — scoped to user, select_related event, newest-first
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_user_interests_scoped_and_ordered(django_user_model):
    user = _make_user(django_user_model, "interest-query-user")
    other = _make_user(django_user_model, "interest-query-other")
    e1 = _make_published_event("Interest E1")
    e2 = _make_published_event("Interest E2")
    e3 = _make_published_event("Interest E3")

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
def test_user_interest_event_ids_bounded(django_user_model):
    user = _make_user(django_user_model, "interest-ids-user")
    other = _make_user(django_user_model, "interest-ids-other")
    e1 = _make_published_event("Interest IDs E1")
    e2 = _make_published_event("Interest IDs E2")
    e3 = _make_published_event("Interest IDs E3")

    i1 = EventInterest.objects.create(user=user, event=e1)
    EventInterest.objects.create(user=user, event=e2)
    EventInterest.objects.create(user=other, event=e3)

    result = user_interest_event_ids(user, event_ids=[e1.id, e3.id])

    assert result == {e1.id: i1.pk}


@pytest.mark.django_db
def test_user_interest_event_ids_unbounded(django_user_model):
    user = _make_user(django_user_model, "interest-ids-unbound-user")
    e1 = _make_published_event("Interest Unbound E1")
    e2 = _make_published_event("Interest Unbound E2")

    i1 = EventInterest.objects.create(user=user, event=e1)
    i2 = EventInterest.objects.create(user=user, event=e2)

    result = user_interest_event_ids(user)

    assert result == {e1.id: i1.pk, e2.id: i2.pk}


# ---------------------------------------------------------------------------
# user_interest_count
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_interest_count(django_user_model):
    user = _make_user(django_user_model, "interest-count-user")
    other = _make_user(django_user_model, "interest-count-other")
    e1 = _make_published_event("Interest Count E1")
    e2 = _make_published_event("Interest Count E2")
    e3 = _make_published_event("Interest Count E3")

    EventInterest.objects.create(user=user, event=e1)
    EventInterest.objects.create(user=user, event=e2)
    EventInterest.objects.create(user=other, event=e3)

    assert user_interest_count(user) == 2
