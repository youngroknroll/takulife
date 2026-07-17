"""Tests for the archive visits page (core.views.archive_visits).

Behavior under test: the event dropdown for adding a visit record offers only
events the user registered as 방문 예정 (raw planned status), not every published
event.
"""
import pytest
from django.test import Client

from archive.models import PersonalEntry, UserEventStatus

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveVisitsSelectableEvents:
    def test_방문_기록_추가_드롭다운은_사용자가_방문_예정으로_등록한_행사만_보여준다(self, make_user, make_event, make_status):
        user = make_user()
        planned = make_event(title="Planned event")
        make_event(title="Other published event")  # published but not planned
        make_status(user, event=planned, status=UserEventStatus.Status.PLANNED)

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        assert resp.status_code == 200
        selectable = list(resp.context["selectable_events"])
        assert selectable == [planned]

    def test_방문_기록_추가_드롭다운에서_이미_다녀왔거나_놓친_행사는_선택할_수_없다(self, make_user, make_event, make_status):
        user = make_user()
        planned = make_event(title="Planned")
        visited = make_event(title="Visited")
        make_status(user, event=planned, status=UserEventStatus.Status.PLANNED)
        make_status(user, event=visited, status=UserEventStatus.Status.VISITED)

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        titles = [e.title for e in resp.context["selectable_events"]]
        assert titles == ["Planned"]

    def test_방문_기록_추가_드롭다운은_직접_등록한_굿즈_항목을_제외한다(self, make_user, make_entry):
        # GOODS is no longer a valid visit subject (collection domain plan
        # §3-3) — must never appear in the inline dropdown, even for a legacy
        # row created before the write path was closed.
        user = make_user()
        place = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="내 장소")
        make_entry(user, kind="goods", title="내 굿즈")

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        entries = list(resp.context["selectable_personal_entries"])
        assert entries == [place]


@pytest.mark.django_db
class TestArchiveVisitsCategoryFilter:
    def test_다녀온_기록_카테고리_목록은_행사와_직접_등록_항목_카테고리를_중복없이_모으고_비공식_여부를_표시한다(self, make_user, make_event, make_visit, make_entry):
        user = make_user()
        popup = make_event(title="Popup", category="popup_store")
        cafe = make_event(title="Cafe", category="collaboration_cafe")
        make_visit(user, event=popup, visited_on="2026-05-20")
        make_visit(user, event=cafe, visited_on="2026-05-22")
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="개인 카페", category="콜라보 카페")
        make_visit(user, personal_entry=entry, visited_on="2026-05-25")

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        assert resp.status_code == 200
        # first-seen order, deduped (콜라보 카페 appears via both cafe event and entry)
        assert resp.context["categories"] == ["콜라보 카페", "팝업스토어"]
        assert resp.context["has_unofficial"] is True

    def test_직접_등록_항목이_없으면_다녀온_기록에_비공식_방문이_없다고_표시한다(self, make_user, make_event, make_visit):
        user = make_user()
        event = make_event(title="Popup", category="popup_store")
        make_visit(user, event=event, visited_on="2026-05-20")

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/")

        assert resp.context["categories"] == ["팝업스토어"]
        assert resp.context["has_unofficial"] is False
