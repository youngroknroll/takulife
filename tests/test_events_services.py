import pytest

from events.models import Event
from events.services import MissingOfficialUrlError, create_published_event


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
