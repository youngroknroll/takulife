"""읽기 전용 방문 기록 상세 페이지(core.views, URL name "archive-visit-detail-page")
테스트.

본인 소유 기록만 접근 가능하며, 대상·날짜·메모·사진과 해당 방문에서 획득한
CollectionItem 목록(CollectionItem.visit_record == 해당 기록)을 보여준다.
"""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveVisitDetailView:
    def test_본인_방문_기록_상세를_열면_대상_날짜_메모_연결_굿즈가_표시된다(
        self, make_user, make_event, make_visit, make_collection_item
    ):
        # VD-1
        user = make_user()
        event = make_event(title="내가 다녀온 행사")
        record = make_visit(user, event=event, visited_on="2026-05-26", short_review="즐거웠다")
        make_collection_item(user, name="현장 구매 굿즈", visit_record=record)

        client = Client()
        client.force_login(user)
        resp = client.get(reverse("archive-visit-detail-page", args=[record.pk]))

        assert resp.status_code == 200
        assert resp.context["record_id"] == record.pk
        assert resp.context["subject"]["title"] == "내가 다녀온 행사"
        assert str(resp.context["visited_on"]) == "2026-05-26"
        assert resp.context["short_review"] == "즐거웠다"
        assert "현장 구매 굿즈".encode() in resp.content

    def test_타인의_방문_기록_상세에_접근하면_404가_반환된다(self, make_user, make_event, make_visit):
        # VD-2
        owner = make_user()
        attacker = make_user()
        record = make_visit(owner, event=make_event(), visited_on="2026-05-26")

        client = Client()
        client.force_login(attacker)
        resp = client.get(reverse("archive-visit-detail-page", args=[record.pk]))

        assert resp.status_code == 404

    def test_비로그인_사용자가_방문_기록_상세를_열면_로그인_페이지로_리다이렉트된다(
        self, make_user, make_event, make_visit
    ):
        # VD-3
        record = make_visit(make_user(), event=make_event(), visited_on="2026-05-26")

        resp = Client().get(reverse("archive-visit-detail-page", args=[record.pk]))

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url
