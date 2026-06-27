"""Tests for the archive visits page (core.views.archive_visits).

Behavior under test: the event dropdown for adding a visit record offers only
events the user registered as 방문 예정 (raw planned status), not every published
event.
"""
import pytest
from django.test import Client

from archive.models import UserEventStatus


@pytest.mark.django_db
class TestArchiveVisitsSelectableEvents:
    def test_dropdown_lists_only_user_planned_events(self, make_user, make_event):
        user = make_user()
        planned = make_event(title="Planned event")
        make_event(title="Other published event")  # published but not planned
        UserEventStatus.objects.create(
            user=user, event=planned, status=UserEventStatus.Status.PLANNED
        )

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        assert resp.status_code == 200
        selectable = list(resp.context["selectable_events"])
        assert selectable == [planned]

    def test_visited_and_missed_events_are_not_selectable(self, make_user, make_event):
        user = make_user()
        planned = make_event(title="Planned")
        visited = make_event(title="Visited")
        UserEventStatus.objects.create(
            user=user, event=planned, status=UserEventStatus.Status.PLANNED
        )
        UserEventStatus.objects.create(
            user=user, event=visited, status=UserEventStatus.Status.VISITED
        )

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        titles = [e.title for e in resp.context["selectable_events"]]
        assert titles == ["Planned"]
