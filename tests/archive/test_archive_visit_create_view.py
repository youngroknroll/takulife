"""Tests for the dedicated visit-record write page (core.views.archive_visit_create).

Behavior under test: a focused create page at /archive/visits/new/ that renders
the same subject choices as the inline form used to (own planned events + own
personal entries), gated by login.
"""
import pytest
from django.test import Client

from archive.models import UserEventStatus

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveVisitCreateView:
    def test_로그인한_사용자가_방문_기록_작성_페이지에_접근하면_작성_페이지가_렌더링된다(self, make_user):
        client = Client()
        client.force_login(make_user())

        resp = client.get("/archive/visits/new/")

        assert resp.status_code == 200
        assert "core/archive/visit_create.html" in [t.name for t in resp.templates]

    def test_비로그인_사용자가_방문_기록_작성_페이지에_접근하면_로그인_페이지로_리다이렉트된다(self):
        resp = Client().get("/archive/visits/new/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url

    def test_방문_기록_작성_페이지는_본인이_참석_예정으로_등록한_행사만_선택_목록에_표시한다(self, make_user, make_event, make_status):
        user = make_user()
        planned = make_event(title="Planned")
        make_event(title="Other published")  # published, not planned
        make_status(user, event=planned, status=UserEventStatus.Status.PLANNED)

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/new/")

        assert list(resp.context["selectable_events"]) == [planned]

    def test_방문_기록_작성_페이지는_본인의_장소_항목만_선택_목록에_표시하고_굿즈는_제외한다(self, make_user, make_entry):
        user = make_user()
        other = make_user(username="other")
        mine = make_entry(user, kind="place", title="내 장소")
        make_entry(other, kind="place", title="남의 카페")
        # GOODS is no longer a valid visit subject (collection domain plan
        # §3-3) — must never appear in the selectable dropdown, even for a
        # legacy row created before the write path was closed.
        make_entry(user, kind="goods", title="내 굿즈")

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

    def test_게시된_행사를_subject로_지정해_접근하면_해당_행사로_대상이_고정된다(self, user_client, make_event):
        _, client = user_client()
        event = make_event(title="방문 완료한 행사")

        resp = client.get(f"/archive/visits/new/?subject=event:{event.id}")

        assert resp.context["preselect"] == {
            "value": f"event:{event.id}",
            "label": "방문 완료한 행사",
        }
        assert b'name="subject"' in resp.content
        assert f"event:{event.id}".encode() in resp.content

    def test_본인의_장소_항목을_subject로_지정해_접근하면_해당_항목으로_대상이_고정된다(self, user_client, make_entry):
        user, client = user_client()
        entry = make_entry(user, kind="place", title="숨은 카페")

        resp = client.get(f"/archive/visits/new/?subject=personal:{entry.id}")

        assert resp.context["preselect"] == {
            "value": f"personal:{entry.id}",
            "label": "숨은 카페",
        }

    def test_굿즈_항목을_subject로_지정해_접근하면_사전_선택이_무시된다(self, user_client, make_entry):
        # GOODS is no longer a valid visit subject (collection domain plan
        # §3-3) — a crafted/legacy ?subject=personal:<goods id> must not lock
        # the form onto it.
        user, client = user_client()
        entry = make_entry(user, kind="goods", title="굿즈")

        resp = client.get(f"/archive/visits/new/?subject=personal:{entry.id}")

        assert resp.context["preselect"] is None

    def test_미게시_행사를_subject로_지정해_접근하면_사전_선택이_무시된다(self, user_client, make_draft_event):
        _, client = user_client()
        draft = make_draft_event(title="비공개 행사")

        resp = client.get(f"/archive/visits/new/?subject=event:{draft.id}")

        assert resp.context["preselect"] is None

    def test_타인의_개인_항목을_subject로_지정해_접근하면_사전_선택이_무시된다(self, user_client, make_user, make_entry):
        _, client = user_client()
        other = make_user(username="stranger")
        entry = make_entry(other, kind="goods", title="남의 굿즈")

        resp = client.get(f"/archive/visits/new/?subject=personal:{entry.id}")

        assert resp.context["preselect"] is None

    def test_잘못된_형식의_subject_값으로_접근해도_오류_없이_사전_선택이_무시된다(self, user_client):
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

    def test_subject_파라미터_없이_접근하면_선택_목록이_그대로_유지된다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/new/")

        assert resp.context["preselect"] is None
        assert "selectable_events" in resp.context
