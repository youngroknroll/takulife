"""archive 도메인 픽스처: 느슨하게 결합된 레코드 팩토리 모음.

루트 conftest의 팩토리 패턴(호출 가능 객체를 반환하는 픽스처, kwargs로 덮어쓰기)을
archive의 네 모델과 방문 사진에 맞춰 따른다. 각 팩토리는 소유 user를(관련 있으면
event/personal_entry 대상도) 명시적으로 받아, 호출부가 '대상은 정확히 하나'
규칙을 직접 통제하게 한다.

팩토리 간 시그니처가 다른 것은 의도된 설계다: make_status/make_interest는
event 전용 모델이라 `event`를 위치/키워드 겸용으로 받고, make_visit은
VisitRecord가 event/personal_entry 둘 중 하나이므로 `*` 뒤 키워드 전용으로
받아 호출자가 어느 쪽인지 명시하게 강제한다. make_entry의 `kind`/`title`는
선택할 대상이 없는 자체 설정값이라 가독성을 위해 키워드 전용으로 뒀다.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)


@pytest.fixture
def make_status(db):
    def _make(user, event=None, status=UserEventStatus.Status.PLANNED, **kwargs):
        return UserEventStatus.objects.create(user=user, event=event, status=status, **kwargs)

    return _make


@pytest.fixture
def make_visit(db):
    def _make(user, *, event=None, personal_entry=None, visited_on, **kwargs):
        return VisitRecord.objects.create(
            user=user, event=event, personal_entry=personal_entry, visited_on=visited_on, **kwargs
        )

    return _make


@pytest.fixture
def make_entry(db):
    def _make(user, *, kind=PersonalEntry.Kind.PLACE, title="개인 항목", **kwargs):
        return PersonalEntry.objects.create(user=user, kind=kind, title=title, **kwargs)

    return _make


@pytest.fixture
def make_interest(db):
    def _make(user, event=None, **kwargs):
        return EventInterest.objects.create(user=user, event=event, **kwargs)

    return _make


@pytest.fixture
def make_collection_item(db):
    def _make(user, *, name="수집 항목", **kwargs):
        return CollectionItem.objects.create(user=user, name=name, **kwargs)

    return _make


@pytest.fixture
def make_visit_photo(db, png_bytes):
    def _make(visit_record, *, filename="photo.png", **kwargs):
        image = SimpleUploadedFile(filename, png_bytes(), content_type="image/png")
        return VisitRecordPhoto.objects.create(visit_record=visit_record, image=image, **kwargs)

    return _make


@pytest.fixture
def make_entries(make_entry):
    """"<title_prefix> 00", "<title_prefix> 01", ... 형태 제목의 PersonalEntry N개."""
    def _make(user, count, *, title_prefix="항목", **kwargs):
        return [make_entry(user, title=f"{title_prefix} {i:02d}", **kwargs) for i in range(count)]

    return _make


@pytest.fixture
def make_statuses(make_status, make_event):
    """"<title_prefix> 00", ... 제목으로 새로 만든 Event마다 하나씩, UserEventStatus N개."""
    def _make(user, count, *, title_prefix="Event", **kwargs):
        return [
            make_status(user, make_event(title=f"{title_prefix} {i:02d}"), **kwargs)
            for i in range(count)
        ]

    return _make


@pytest.fixture
def make_visits(make_visit, make_event):
    """"<title_prefix> 00", ... 제목으로 새로 만든 Event마다 하나씩, VisitRecord N개."""
    def _make(user, count, *, title_prefix="Visit", **kwargs):
        kwargs.setdefault("visited_on", "2026-01-01")
        return [
            make_visit(user, event=make_event(title=f"{title_prefix} {i:02d}"), **kwargs)
            for i in range(count)
        ]

    return _make
