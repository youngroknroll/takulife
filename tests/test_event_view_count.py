"""Tests for view-count tracking on event detail pages.

Covers:
- New Event has view_count default of 0.
- GET /events/<id>/ twice increments DB view_count to 2.
- GET /events/<draft_id>/ returns 404 and does NOT increment view_count.
"""
import pytest
from django.test import Client

from events.models import Event


def make_event(**kwargs):
    defaults = {"title": "Test Event", "publish_status": Event.PublishStatus.PUBLISHED}
    defaults.update(kwargs)
    return Event.objects.create(**defaults)


@pytest.mark.django_db
class TestViewCountDefault:
    def test_new_event_has_view_count_zero(self):
        event = make_event()
        assert event.view_count == 0


@pytest.mark.django_db
class TestViewCountIncrement:
    def test_two_detail_gets_increment_view_count_to_two(self):
        event = make_event()
        client = Client()

        client.get(f"/events/{event.pk}/")
        client.get(f"/events/{event.pk}/")

        event.refresh_from_db()
        assert event.view_count == 2

    def test_draft_detail_returns_404_and_does_not_increment(self):
        event = make_event(publish_status=Event.PublishStatus.DRAFT)
        client = Client()

        resp = client.get(f"/events/{event.pk}/")

        assert resp.status_code == 404
        event.refresh_from_db()
        assert event.view_count == 0
