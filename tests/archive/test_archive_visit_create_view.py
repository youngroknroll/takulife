"""Tests for the dedicated visit-record write page (core.views.archive_visit_create).

Behavior under test: a focused create page at /archive/visits/new/ that renders
the same subject choices as the inline form used to (own planned events + own
personal entries), gated by login.
"""
import pytest
from django.test import Client

from archive.models import UserEventStatus


@pytest.mark.django_db
class TestArchiveVisitCreateView:
    def test_authenticated_user_gets_write_page(self, make_user):
        client = Client()
        client.force_login(make_user())

        resp = client.get("/archive/visits/new/")

        assert resp.status_code == 200
        assert "core/archive/visit_create.html" in [t.name for t in resp.templates]

    def test_anonymous_user_redirected_to_login(self):
        resp = Client().get("/archive/visits/new/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url

    def test_selectable_events_only_own_planned(self, make_user, make_event, make_status):
        user = make_user()
        planned = make_event(title="Planned")
        make_event(title="Other published")  # published, not planned
        make_status(user, event=planned, status=UserEventStatus.Status.PLANNED)

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/new/")

        assert list(resp.context["selectable_events"]) == [planned]

    def test_selectable_personal_entries_scoped_to_user(self, make_user, make_entry):
        user = make_user()
        other = make_user(username="other")
        mine = make_entry(user, kind="place", title="내 장소")
        make_entry(other, kind="place", title="남의 카페")

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/new/")

        entries = list(resp.context["selectable_personal_entries"])
        assert entries == [mine]


@pytest.mark.django_db
class TestArchiveVisitCreatePreselect:
    """?subject=event:<id> / personal:<id> locks the write form to one subject.

    Lets a 방문 완료 행사's 기록 button open the page ready to save, even though a
    visited event is absent from the planned-only dropdown.
    """

    def test_preselect_published_event_locks_subject(self, user_client, make_event):
        _, client = user_client()
        event = make_event(title="방문 완료한 행사")

        resp = client.get(f"/archive/visits/new/?subject=event:{event.id}")

        assert resp.context["preselect"] == {
            "value": f"event:{event.id}",
            "label": "방문 완료한 행사",
        }
        assert b'name="subject"' in resp.content
        assert f"event:{event.id}".encode() in resp.content

    def test_preselect_own_personal_entry(self, user_client, make_entry):
        user, client = user_client()
        entry = make_entry(user, kind="place", title="숨은 카페")

        resp = client.get(f"/archive/visits/new/?subject=personal:{entry.id}")

        assert resp.context["preselect"] == {
            "value": f"personal:{entry.id}",
            "label": "숨은 카페",
        }

    def test_preselect_unpublished_event_ignored(self, user_client, make_draft_event):
        _, client = user_client()
        draft = make_draft_event(title="비공개 행사")

        resp = client.get(f"/archive/visits/new/?subject=event:{draft.id}")

        assert resp.context["preselect"] is None

    def test_preselect_other_users_personal_entry_ignored(self, user_client, make_user, make_entry):
        _, client = user_client()
        other = make_user(username="stranger")
        entry = make_entry(other, kind="goods", title="남의 굿즈")

        resp = client.get(f"/archive/visits/new/?subject=personal:{entry.id}")

        assert resp.context["preselect"] is None

    def test_preselect_malformed_param_ignored(self, user_client):
        _, client = user_client()

        # Includes crafted vectors that pass a naive isdigit() guard but would
        # crash int()/the ORM: a non-ASCII "digit" and an oversized id.
        for raw in (
            "garbage",
            "event:",
            "event:abc",
            "weird:1",
            "event:²",  # superscript two — isdigit() True, int() raises
            "event:" + "9" * 30,  # past the DB integer range
        ):
            resp = client.get(f"/archive/visits/new/?subject={raw}")
            assert resp.status_code == 200
            assert resp.context["preselect"] is None

    def test_no_subject_param_keeps_dropdown(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/new/")

        assert resp.context["preselect"] is None
        assert "selectable_events" in resp.context
