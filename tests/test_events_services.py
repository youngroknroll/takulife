import pytest

from events.models import Event
from events.services import (
    DuplicateOfficialUrlError,
    MissingOfficialUrlError,
    PublishEventError,
    create_published_event,
)


@pytest.mark.django_db
def test_create_published_event_rejects_none_official_url():
    with pytest.raises(MissingOfficialUrlError):
        create_published_event(title="Event", official_url=None)


@pytest.mark.django_db
def test_create_published_event_rejects_blank_official_url():
    with pytest.raises(MissingOfficialUrlError):
        create_published_event(title="Event", official_url="   ")


@pytest.mark.django_db
def test_create_published_event_creates_published_event_with_official_url():
    event = create_published_event(title="Event", official_url="https://example.com/event")

    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.official_url == "https://example.com/event"


@pytest.mark.django_db
def test_create_published_event_maps_duplicate_url_to_domain_error():
    Event.objects.create(
        title="Existing event",
        official_url="https://example.com/event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    with pytest.raises(DuplicateOfficialUrlError):
        create_published_event(title="Duplicate", official_url="https://example.com/event")


@pytest.mark.django_db
def test_create_published_event_maps_unexpected_error_to_publish_event_error(monkeypatch):
    def raise_runtime_error(**kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("events.services.Event.objects.create", raise_runtime_error)

    with pytest.raises(PublishEventError):
        create_published_event(title="Event", official_url="https://example.com/event")
