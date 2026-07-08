"""Tests for the event_detail HTML view, including the authenticated branch.

The logged-in path (a viewer's own status/interest reflected on a public event
page) was uncovered: anonymous viewers exercised only the empty defaults.
"""
import pytest
from django.test import Client

from archive.models import EventInterest, UserEventStatus


@pytest.mark.django_db
class TestEventDetailView:
    def test_anonymous_sees_empty_user_state(self, make_event):
        event = make_event(title="공개 행사")
        resp = Client().get(f"/events/{event.id}/")

        assert resp.status_code == 200
        assert resp.context["event"] == event
        assert resp.context["user_status"] == ""
        assert resp.context["user_interested"] is False

    def test_authenticated_viewer_sees_own_status_and_interest(
        self, make_event, make_user
    ):
        event = make_event(title="내 상태 있는 행사")
        user = make_user()
        UserEventStatus.objects.create(user=user, event=event, status="planned")
        interest = EventInterest.objects.create(user=user, event=event)

        client = Client()
        client.force_login(user)
        resp = client.get(f"/events/{event.id}/")

        assert resp.status_code == 200
        assert resp.context["user_status"] == "planned"
        assert resp.context["user_interested"] is True
        assert resp.context["user_interest_id"] == interest.id

    def test_authenticated_viewer_without_status_stays_empty(
        self, make_event, make_user
    ):
        event = make_event(title="상태 없는 행사")
        client = Client()
        client.force_login(make_user())

        resp = client.get(f"/events/{event.id}/")

        assert resp.status_code == 200
        assert resp.context["user_status"] == ""
        assert resp.context["user_interested"] is False

    def test_unpublished_event_returns_404(self, make_draft_event):
        draft = make_draft_event(title="미게시")
        resp = Client().get(f"/events/{draft.id}/")
        assert resp.status_code == 404

    def test_missing_event_returns_404(self):
        resp = Client().get("/events/999999/")
        assert resp.status_code == 404
