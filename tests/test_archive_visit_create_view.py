"""Tests for the dedicated visit-record write page (core.views.archive_visit_create).

Behavior under test: a focused create page at /archive/visits/new/ that renders
the same subject choices as the inline form used to (own planned events + own
personal entries), gated by login.
"""
import pytest
from django.test import Client

from archive.models import PersonalEntry, UserEventStatus


@pytest.mark.django_db
class TestArchiveVisitCreateView:
    def test_authenticated_user_gets_write_page(self, make_user):
        client = Client()
        client.force_login(make_user())

        resp = client.get("/archive/visits/new/")

        assert resp.status_code == 200
        assert "core/archive_visit_create.html" in [t.name for t in resp.templates]

    def test_anonymous_user_redirected_to_login(self):
        resp = Client().get("/archive/visits/new/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url

    def test_selectable_events_only_own_planned(self, make_user, make_event):
        user = make_user()
        planned = make_event(title="Planned")
        make_event(title="Other published")  # published, not planned
        UserEventStatus.objects.create(
            user=user, event=planned, status=UserEventStatus.Status.PLANNED
        )

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/new/")

        assert list(resp.context["selectable_events"]) == [planned]

    def test_selectable_personal_entries_scoped_to_user(self, make_user):
        user = make_user()
        other = make_user(username="other")
        mine = PersonalEntry.objects.create(user=user, kind="goods", title="내 굿즈")
        PersonalEntry.objects.create(user=other, kind="place", title="남의 카페")

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/new/")

        entries = list(resp.context["selectable_personal_entries"])
        assert entries == [mine]
