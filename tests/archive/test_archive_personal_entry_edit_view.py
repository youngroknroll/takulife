"""Tests for the personal-entry (unofficial place) edit page.

Split into its own file rather than folded into
test_archive_personal_entry_detail_view.py, mirroring how the sibling
collection domain keeps detail and edit in separate files
(test_archive_collection_detail_view.py / test_archive_collection_edit_view.py)
even though both target the same aggregate.
"""
import pytest
from django.test import Client

from core.vocab import PERSONAL_ENTRY_CATEGORY_SUGGESTIONS

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchivePersonalEntryEditView:
    def test_본인_소유_비공식_장소의_수정_페이지를_열면_기존_값이_컨텍스트로_전달된다(
        self, user_client, make_entry
    ):
        # PDE-1
        user, client = user_client()
        entry = make_entry(
            user,
            title="숨겨진 골목 소품샵",
            category="장소",
            work_title="작품A",
            location_name="서울 홍대입구역 인근",
            region="서울",
            url="https://example.com/place",
            memo="주말 오후에만 문을 연다",
        )

        resp = client.get(f"/archive/personal/{entry.id}/edit/")

        assert resp.status_code == 200
        assert "core/archive/personal_edit.html" in [t.name for t in resp.templates]
        assert resp.context["entry"] == entry

    def test_수정_페이지를_열면_카테고리_추천_칩_목록이_컨텍스트로_전달된다(
        self, user_client, make_entry
    ):
        # PDE-4
        user, client = user_client()
        entry = make_entry(user, title="카테고리 추천 확인용 장소")

        resp = client.get(f"/archive/personal/{entry.id}/edit/")

        assert (
            resp.context["PERSONAL_ENTRY_CATEGORY_SUGGESTIONS"]
            == PERSONAL_ENTRY_CATEGORY_SUGGESTIONS
        )

    def test_타인_소유_비공식_장소의_수정_페이지에_접근하면_404가_반환된다(
        self, make_user, user_client, make_entry
    ):
        # PDE-2
        owner = make_user()
        entry = make_entry(owner, title="소유자 전용 비공식 장소")
        _, client = user_client()

        resp = client.get(f"/archive/personal/{entry.id}/edit/")

        assert resp.status_code == 404

    def test_비로그인_사용자가_비공식_장소_수정_페이지를_열면_로그인_페이지로_리다이렉트된다(
        self, make_user, make_entry
    ):
        # PDE-3
        entry = make_entry(make_user(), title="비로그인 접근 비공식 장소")

        resp = Client().get(f"/archive/personal/{entry.id}/edit/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url
