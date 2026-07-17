"""Tests for view-count tracking on event detail pages.

Covers:
- New Event has view_count default of 0.
- GET /events/<id>/ twice increments DB view_count to 2.
- GET /events/<draft_id>/ returns 404 and does NOT increment view_count.
"""
import pytest
from django.test import Client

from events.models import Event


@pytest.mark.django_db
class TestViewCountDefault:
    pytestmark = pytest.mark.domain

    def test_새로_생성된_행사의_조회수는_0이다(self, make_event):
        event = make_event()
        assert event.view_count == 0


@pytest.mark.django_db
class TestViewCountIncrement:
    pytestmark = pytest.mark.web

    def test_행사_상세를_두_번_조회하면_조회수가_2로_증가한다(self, make_event):
        event = make_event()
        client = Client()

        client.get(f"/events/{event.pk}/")
        client.get(f"/events/{event.pk}/")

        event.refresh_from_db()
        assert event.view_count == 2

    def test_미게시_행사_상세_조회는_404를_반환하고_조회수를_증가시키지_않는다(self, make_event):
        event = make_event(publish_status=Event.PublishStatus.DRAFT)
        client = Client()

        resp = client.get(f"/events/{event.pk}/")

        assert resp.status_code == 404
        event.refresh_from_db()
        assert event.view_count == 0
