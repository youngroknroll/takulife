"""Unit tests for the archive read layer (archive/queries.py)."""

import pytest

from archive.models import UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_STATUS_SLUGS,
    list_user_statuses,
    list_user_visit_records,
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

    UserEventStatus.objects.create(user=user, event=e1, status="interested")
    UserEventStatus.objects.create(user=user, event=e2, status="visited")
    UserEventStatus.objects.create(user=other, event=e1, status="interested")

    counts = user_status_counts(user)

    assert counts["interested"] == 1
    assert counts["visited"] == 1
    assert counts["planned"] == 0
    assert counts["missed"] == 0


@pytest.mark.django_db
def test_list_user_statuses_filters_by_user_and_status(django_user_model):
    user = _make_user(django_user_model, "list-status-user")
    other = _make_user(django_user_model, "list-status-other")
    e1 = _make_published_event("E1")
    e2 = _make_published_event("E2")

    UserEventStatus.objects.create(user=user, event=e1, status="interested")
    UserEventStatus.objects.create(user=user, event=e2, status="visited")
    UserEventStatus.objects.create(user=other, event=e1, status="interested")

    assert list_user_statuses(user).count() == 2
    interested_only = list_user_statuses(user, "interested")
    assert interested_only.count() == 1
    assert interested_only.first().event_id == e1.id


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
