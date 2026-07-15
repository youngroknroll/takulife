"""staff.services — PR-E3 (hard-delete guard against archive references).

`events/services.py` must never import `archive` (architecture boundary),
so the "does this event have archive references?" question and the guarded
delete orchestration live in staff/services.py instead — staff is the layer
allowed to depend on both events and archive.
"""
import datetime

import pytest

from archive.models import CollectionItem, EventInterest, UserEventStatus, VisitRecord
from events.models import Event
from staff.services import (
    EventHasArchiveReferencesError,
    delete_event,
    event_archive_reference_counts,
)


@pytest.mark.django_db
def test_event_archive_reference_counts_all_zero_for_unreferenced_event(make_event):
    event = make_event(official_url="https://example.com/no-refs")

    counts = event_archive_reference_counts(event=event)

    assert counts == {"interest": 0, "status": 0, "visit": 0, "collection_item": 0}


@pytest.mark.django_db
def test_event_archive_reference_counts_reflects_each_kind(make_event, make_user):
    event = make_event(official_url="https://example.com/with-refs")
    user = make_user()
    EventInterest.objects.create(user=user, event=event)
    UserEventStatus.objects.create(user=user, event=event, status=UserEventStatus.Status.PLANNED)
    VisitRecord.objects.create(user=user, event=event, visited_on=datetime.date(2026, 1, 1))
    CollectionItem.objects.create(user=user, name="집계용 굿즈", event=event)

    counts = event_archive_reference_counts(event=event)

    assert counts == {"interest": 1, "status": 1, "visit": 1, "collection_item": 1}


@pytest.mark.django_db
def test_delete_event_removes_event_with_zero_references(make_event):
    event = make_event(official_url="https://example.com/deletable")
    pk = event.pk

    delete_event(event=event)

    assert not Event.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_delete_event_rejects_event_with_archive_interest_reference(make_event, make_user):
    event = make_event(official_url="https://example.com/blocked-by-interest")
    user = make_user()
    EventInterest.objects.create(user=user, event=event)

    with pytest.raises(EventHasArchiveReferencesError) as exc_info:
        delete_event(event=event)

    assert exc_info.value.interest_count == 1
    assert exc_info.value.status_count == 0
    assert exc_info.value.visit_count == 0
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_delete_event_rejects_event_with_archive_status_reference(make_event, make_user):
    event = make_event(official_url="https://example.com/blocked-by-status")
    user = make_user()
    UserEventStatus.objects.create(user=user, event=event, status=UserEventStatus.Status.PLANNED)

    with pytest.raises(EventHasArchiveReferencesError) as exc_info:
        delete_event(event=event)

    assert exc_info.value.status_count == 1
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_delete_event_rejects_event_with_archive_visit_reference(make_event, make_user):
    event = make_event(official_url="https://example.com/blocked-by-visit")
    user = make_user()
    VisitRecord.objects.create(user=user, event=event, visited_on=datetime.date(2026, 1, 1))

    with pytest.raises(EventHasArchiveReferencesError) as exc_info:
        delete_event(event=event)

    assert exc_info.value.visit_count == 1
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_delete_event_rejects_event_with_collection_item_reference(make_event, make_user):
    event = make_event(official_url="https://example.com/blocked-by-collection-item")
    user = make_user()
    CollectionItem.objects.create(user=user, name="참조 굿즈", event=event)

    with pytest.raises(EventHasArchiveReferencesError) as exc_info:
        delete_event(event=event)

    assert exc_info.value.collection_item_count == 1
    assert Event.objects.filter(pk=event.pk).exists()
