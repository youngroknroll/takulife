"""Tests for the archive visits page (core.views.archive_visits).

Behavior under test: the event dropdown for adding a visit record offers only
events the user registered as 방문 예정 (raw planned status), not every published
event.
"""
import pytest
from django.test import Client

from archive.models import PersonalEntry, UserEventStatus, VisitRecord


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


@pytest.mark.django_db
class TestArchiveVisitsCategoryFilter:
    def test_categories_and_has_unofficial_context(self, make_user, make_event):
        user = make_user()
        popup = make_event(title="Popup", category="popup_store")
        cafe = make_event(title="Cafe", category="collaboration_cafe")
        VisitRecord.objects.create(user=user, event=popup, visited_on="2026-05-20")
        VisitRecord.objects.create(user=user, event=cafe, visited_on="2026-05-22")
        entry = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="개인 카페", category="콜라보 카페"
        )
        VisitRecord.objects.create(user=user, personal_entry=entry, visited_on="2026-05-25")

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        assert resp.status_code == 200
        # first-seen order, deduped (콜라보 카페 appears via both cafe event and entry)
        assert resp.context["categories"] == ["콜라보 카페", "팝업스토어"]
        assert resp.context["has_unofficial"] is True

    def test_has_unofficial_false_without_personal_entries(self, make_user, make_event):
        user = make_user()
        event = make_event(title="Popup", category="popup_store")
        VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-20")

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        assert resp.context["categories"] == ["팝업스토어"]
        assert resp.context["has_unofficial"] is False
