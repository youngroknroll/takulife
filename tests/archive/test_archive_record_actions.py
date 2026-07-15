"""Tests for the 내 아카이브 record-action wiring on the SSR pages.

Behavior under test:
- 기록장 (/archive/) drops the 정리 체크리스트, exposes a working 기록 추가 link,
  and shows a per-row 기록 shortcut only on 방문 완료 (visited) rows.
- 방문 기록 (/archive/visits/) no longer carries the 기록 안내 panel; that guidance
  now lives on the write page (/archive/visits/new/).
"""
import pytest

from archive.models import UserEventStatus


@pytest.mark.django_db
class TestArchiveRecordPageActions:
    def test_checklist_removed(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/")

        assert "정리 체크리스트" not in resp.content.decode()

    def test_add_record_link_present(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/")

        # The disabled "(준비 중)" button is gone; a real link to the write page is in.
        body = resp.content.decode()
        assert "준비 중" not in body
        assert 'href="/archive/visits/new/"' in body

    def test_visited_row_has_record_shortcut(self, user_client, make_event, make_status):
        user, client = user_client()
        event = make_event(title="다녀온 행사")
        make_status(user, event=event, status=UserEventStatus.Status.VISITED)

        resp = client.get("/archive/")

        assert f"/archive/visits/new/?subject=event:{event.id}".encode() in resp.content

    def test_planned_row_has_no_record_shortcut(self, user_client, make_event, make_status):
        user, client = user_client()
        event = make_event(title="갈 예정 행사")
        make_status(user, event=event, status=UserEventStatus.Status.PLANNED)

        resp = client.get("/archive/")

        # The per-row 기록 shortcut carries ?subject=; the generic 기록 추가 link does not.
        assert b"/archive/visits/new/?subject=" not in resp.content


@pytest.mark.django_db
class TestVisitRecordCollectionShortcut:
    """다녀온 기록 (/archive/visits/) 카드에 굿즈 등록 바로가기가 붙는다
    (collection domain design plan §4 PR-C5b-2 CP-V1). 기존 수정/기록 삭제
    액션 옆에 ?visit_record=<id>로 컬렉션 등록 폼을 프리셀렉트하는 링크가
    붙는다 — test_visited_row_has_record_shortcut의 미러."""

    def test_visit_row_has_collection_add_shortcut(self, user_client, make_event, make_visit):
        user, client = user_client()
        event = make_event(title="다녀온 행사")
        record = make_visit(user, event=event, visited_on="2026-05-01")

        resp = client.get("/archive/visits/")

        assert f"/archive/collection/new/?visit_record={record.id}".encode() in resp.content


@pytest.mark.django_db
class TestVisitGuidanceMoved:
    def test_visits_page_drops_guidance_panel(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/")

        assert "기록 안내" not in resp.content.decode()

    def test_write_page_shows_guidance_panel(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/new/")

        assert "기록 안내" in resp.content.decode()
