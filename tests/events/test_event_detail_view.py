"""event_detail HTML 뷰를 검증한다(로그인 분기 포함).

로그인 경로(공개 행사 페이지에 본인 상태/찜 여부가 반영되는지)는 그동안
검증되지 않았다: 비로그인 사용자만 빈 기본값을 확인해왔다.
"""
import pytest
from django.test import Client

from archive.models import EventInterest, UserEventStatus

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestEventDetailView:
    def test_익명_사용자가_행사_상세를_보면_사용자_상태와_찜_여부가_빈_값이다(self, make_event):
        event = make_event(title="공개 행사")
        resp = Client().get(f"/events/{event.id}/")

        assert resp.status_code == 200
        assert resp.context["event"] == event
        assert resp.context["user_status"] == ""
        assert resp.context["user_interested"] is False

    def test_로그인_사용자가_본인이_등록한_상태와_찜이_있는_행사_상세를_보면_본인_값이_반영된다(
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

    def test_로그인_사용자도_등록한_상태와_찜이_없으면_행사_상세에서_빈_값으로_유지된다(
        self, make_event, make_user
    ):
        event = make_event(title="상태 없는 행사")
        client = Client()
        client.force_login(make_user())

        resp = client.get(f"/events/{event.id}/")

        assert resp.status_code == 200
        assert resp.context["user_status"] == ""
        assert resp.context["user_interested"] is False

    def test_미게시_행사_상세를_조회하면_404를_반환한다(self, make_draft_event):
        draft = make_draft_event(title="미게시")
        resp = Client().get(f"/events/{draft.id}/")
        assert resp.status_code == 404

    def test_존재하지_않는_행사_상세를_조회하면_404를_반환한다(self):
        resp = Client().get("/events/999999/")
        assert resp.status_code == 404
