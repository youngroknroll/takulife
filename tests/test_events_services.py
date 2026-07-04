import datetime

import pytest

from events.models import Event
from events.services import (
    DuplicateOfficialUrlError,
    InvalidEventPeriodError,
    MissingOfficialUrlError,
    PublishEventError,
    PublishEventTitleError,
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


@pytest.mark.django_db
def test_create_published_event_rejects_inverted_period():
    with pytest.raises(InvalidEventPeriodError):
        create_published_event(
            title="Event",
            official_url="https://example.com/inverted",
            start_date=datetime.date(2026, 8, 10),
            end_date=datetime.date(2026, 8, 1),
        )


def test_invalid_event_period_error_is_a_publish_event_error():
    assert issubclass(InvalidEventPeriodError, PublishEventError)


def test_publish_event_title_error_is_a_publish_event_error():
    assert issubclass(PublishEventTitleError, PublishEventError)


@pytest.mark.django_db
def test_create_published_event_allows_equal_start_and_end_date():
    event = create_published_event(
        title="Event",
        official_url="https://example.com/same-day",
        start_date=datetime.date(2026, 8, 1),
        end_date=datetime.date(2026, 8, 1),
    )

    assert event.start_date == event.end_date == datetime.date(2026, 8, 1)


@pytest.mark.django_db
def test_create_published_event_allows_start_date_without_end_date():
    event = create_published_event(
        title="Event",
        official_url="https://example.com/open-ended",
        start_date=datetime.date(2026, 8, 1),
    )

    assert event.start_date == datetime.date(2026, 8, 1)
    assert event.end_date is None


@pytest.mark.django_db
def test_create_published_event_rejects_blank_title():
    with pytest.raises(PublishEventTitleError):
        create_published_event(title="", official_url="https://example.com/blank-title")

    assert not Event.objects.filter(official_url="https://example.com/blank-title").exists()


@pytest.mark.django_db
def test_create_published_event_rejects_whitespace_only_title():
    with pytest.raises(PublishEventTitleError):
        create_published_event(title="   ", official_url="https://example.com/whitespace-title")

    assert not Event.objects.filter(official_url="https://example.com/whitespace-title").exists()


@pytest.mark.django_db
def test_create_published_event_rejects_title_equal_to_official_url():
    with pytest.raises(PublishEventTitleError):
        create_published_event(
            title="https://example.com/matching-title",
            official_url="https://example.com/matching-title",
        )

    assert not Event.objects.filter(official_url="https://example.com/matching-title").exists()


@pytest.mark.django_db
def test_create_published_event_rejects_title_matching_official_url_with_trailing_slash_difference():
    with pytest.raises(PublishEventTitleError):
        create_published_event(
            title="https://example.com/slash-title/",
            official_url="https://example.com/slash-title",
        )
    assert not Event.objects.filter(official_url="https://example.com/slash-title").exists()

    with pytest.raises(PublishEventTitleError):
        create_published_event(
            title="https://example.com/slash-title-2",
            official_url="https://example.com/slash-title-2/",
        )
    assert not Event.objects.filter(official_url="https://example.com/slash-title-2/").exists()


@pytest.mark.django_db
def test_create_published_event_allows_title_differing_only_by_case_from_official_url():
    event = create_published_event(
        title="HTTPS://EXAMPLE.COM/case-title",
        official_url="https://example.com/case-title",
    )

    assert event.title == "HTTPS://EXAMPLE.COM/case-title"
    assert event.official_url == "https://example.com/case-title"
