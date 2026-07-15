"""Archive-domain fixtures: loosely-coupled record factories.

Mirrors the root conftest's factory pattern (callable-returning fixtures, kwargs
overrides) for the four archive models plus visit-record photos. Each factory
takes the owning user (and, where relevant, the event/personal_entry subject)
explicitly so call sites keep full control over exactly-one-subject wiring.

Signature asymmetry between the factories is intentional, not an oversight:
make_status/make_interest take `event` as a plain positional-or-keyword
argument because UserEventStatus/EventInterest are event-only models — there
is only one possible subject, so positional use reads naturally. make_visit
takes `event`/`personal_entry` as keyword-only (after `*`) because VisitRecord
is either-or on its subject, and keyword-only forces the caller to name which
one they mean instead of relying on position. make_entry's keyword-only
`kind`/`title` are keyword-only for a different reason — PersonalEntry has no
event/personal_entry choice at all, they are just its own config fields with
defaults, kept keyword-only for readability at the call site.
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
    """N PersonalEntry rows titled "<title_prefix> 00", "<title_prefix> 01", ..."""
    def _make(user, count, *, title_prefix="항목", **kwargs):
        return [make_entry(user, title=f"{title_prefix} {i:02d}", **kwargs) for i in range(count)]

    return _make


@pytest.fixture
def make_statuses(make_status, make_event):
    """N UserEventStatus rows, one per freshly-made Event titled "<title_prefix> 00", ..."""
    def _make(user, count, *, title_prefix="Event", **kwargs):
        return [
            make_status(user, make_event(title=f"{title_prefix} {i:02d}"), **kwargs)
            for i in range(count)
        ]

    return _make


@pytest.fixture
def make_visits(make_visit, make_event):
    """N VisitRecord rows, one per freshly-made Event titled "<title_prefix> 00", ..."""
    def _make(user, count, *, title_prefix="Visit", **kwargs):
        kwargs.setdefault("visited_on", "2026-01-01")
        return [
            make_visit(user, event=make_event(title=f"{title_prefix} {i:02d}"), **kwargs)
            for i in range(count)
        ]

    return _make
