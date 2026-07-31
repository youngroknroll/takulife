"""아카이브 참조를 지키는 하드 삭제 가드 검증.

`events/services.py`는 `archive`를 임포트하면 안 되는 아키텍처 경계가 있어,
참조 여부 판단과 삭제 가드 로직은 events와 archive 양쪽에 의존해도 되는
staff/services.py에 둔다.
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

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_아카이브_참조가_없는_행사는_참조_집계가_모두_0이다(make_event):
    event = make_event(official_url="https://example.com/no-refs")

    counts = event_archive_reference_counts(event=event)

    assert counts == {"interest": 0, "status": 0, "visit": 0, "collection_item": 0}


@pytest.mark.django_db
def test_아카이브_참조_종류별로_존재하면_집계에_각각_반영된다(make_event, make_user):
    event = make_event(official_url="https://example.com/with-refs")
    user = make_user()
    EventInterest.objects.create(user=user, event=event)
    UserEventStatus.objects.create(user=user, event=event, status=UserEventStatus.Status.PLANNED)
    VisitRecord.objects.create(user=user, event=event, visited_on=datetime.date(2026, 1, 1))
    CollectionItem.objects.create(user=user, name="집계용 굿즈", event=event)

    counts = event_archive_reference_counts(event=event)

    assert counts == {"interest": 1, "status": 1, "visit": 1, "collection_item": 1}


@pytest.mark.django_db
def test_아카이브_참조가_없는_행사를_삭제하면_실제로_제거된다(make_event):
    event = make_event(official_url="https://example.com/deletable")
    pk = event.pk

    delete_event(event=event)

    assert not Event.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_관심_참조가_있는_행사를_삭제하면_거부되고_관심_건수가_예외에_담긴다(make_event, make_user):
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
def test_방문상태_참조가_있는_행사를_삭제하면_거부되고_상태_건수가_예외에_담긴다(make_event, make_user):
    event = make_event(official_url="https://example.com/blocked-by-status")
    user = make_user()
    UserEventStatus.objects.create(user=user, event=event, status=UserEventStatus.Status.PLANNED)

    with pytest.raises(EventHasArchiveReferencesError) as exc_info:
        delete_event(event=event)

    assert exc_info.value.status_count == 1
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_방문기록_참조가_있는_행사를_삭제하면_거부되고_방문_건수가_예외에_담긴다(make_event, make_user):
    event = make_event(official_url="https://example.com/blocked-by-visit")
    user = make_user()
    VisitRecord.objects.create(user=user, event=event, visited_on=datetime.date(2026, 1, 1))

    with pytest.raises(EventHasArchiveReferencesError) as exc_info:
        delete_event(event=event)

    assert exc_info.value.visit_count == 1
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_컬렉션_항목_참조가_있는_행사를_삭제하면_거부되고_컬렉션_항목_건수가_예외에_담긴다(make_event, make_user):
    event = make_event(official_url="https://example.com/blocked-by-collection-item")
    user = make_user()
    CollectionItem.objects.create(user=user, name="참조 굿즈", event=event)

    with pytest.raises(EventHasArchiveReferencesError) as exc_info:
        delete_event(event=event)

    assert exc_info.value.collection_item_count == 1
    assert Event.objects.filter(pk=event.pk).exists()
