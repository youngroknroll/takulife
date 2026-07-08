"""Tests for the 내 아카이브 record-action wiring on the SSR pages.

Behavior under test:
- 기록장 (/archive/) drops the 정리 체크리스트, exposes a working 기록 추가 link,
  and shows a per-row 기록 shortcut only on 방문 완료 (visited) rows.
- 방문 기록 (/archive/visits/) no longer carries the 기록 안내 panel; that guidance
  now lives on the write page (/archive/visits/new/).
"""
import pytest
from django.test import Client

from archive.models import UserEventStatus


def _login(make_user):
    user = make_user()
    client = Client()
    client.force_login(user)
    return user, client


@pytest.mark.django_db
class TestArchiveRecordPageActions:
    def test_checklist_removed(self, make_user):
        _, client = _login(make_user)

        resp = client.get("/archive/")

        assert "정리 체크리스트" not in resp.content.decode()

    def test_add_record_link_present(self, make_user):
        _, client = _login(make_user)

        resp = client.get("/archive/")

        # The disabled "(준비 중)" button is gone; a real link to the write page is in.
        body = resp.content.decode()
        assert "준비 중" not in body
        assert 'href="/archive/visits/new/"' in body

    def test_visited_row_has_record_shortcut(self, make_user, make_event):
        user, client = _login(make_user)
        event = make_event(title="다녀온 행사")
        UserEventStatus.objects.create(
            user=user, event=event, status=UserEventStatus.Status.VISITED
        )

        resp = client.get("/archive/")

        assert f"/archive/visits/new/?subject=event:{event.id}".encode() in resp.content

    def test_planned_row_has_no_record_shortcut(self, make_user, make_event):
        user, client = _login(make_user)
        event = make_event(title="갈 예정 행사")
        UserEventStatus.objects.create(
            user=user, event=event, status=UserEventStatus.Status.PLANNED
        )

        resp = client.get("/archive/")

        # The per-row 기록 shortcut carries ?subject=; the generic 기록 추가 link does not.
        assert b"/archive/visits/new/?subject=" not in resp.content


@pytest.mark.django_db
class TestVisitGuidanceMoved:
    def test_visits_page_drops_guidance_panel(self, make_user):
        _, client = _login(make_user)

        resp = client.get("/archive/visits/")

        assert "기록 안내" not in resp.content.decode()

    def test_write_page_shows_guidance_panel(self, make_user):
        _, client = _login(make_user)

        resp = client.get("/archive/visits/new/")

        assert "기록 안내" in resp.content.decode()
