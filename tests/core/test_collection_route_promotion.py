"""IA-1 라우트 승격(목표 IA 계획 D1, .docs/plans/2026-07-16-target-ia-plan.md
§4): /collection/, /collection/new/, /collection/<id>/edit/는 기존
core.views.archive_collection_items / archive_collection_item_create /
archive_collection_item_edit 뷰를 그대로 제공하고(같은 뷰 객체, 라우트만
이동), 옛 /archive/collection/* 경로는 쿼리스트링을 보존한 채 새 경로로
302 리다이렉트된다.
"""
import pytest

from archive.models import CollectionItem

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestCollectionRoutesPromoted:
    def test_컬렉션_목록_경로는_기존_뷰를_그대로_제공한다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/")

        assert resp.status_code == 200
        assert "core/archive/collection.html" in [t.name for t in resp.templates]

    def test_컬렉션_등록_경로는_기존_뷰를_그대로_제공한다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")

        assert resp.status_code == 200
        assert "core/archive/collection_create.html" in [t.name for t in resp.templates]

    def test_컬렉션_수정_경로는_기존_뷰를_그대로_제공한다(self, user_client):
        user, client = user_client()
        item = CollectionItem.objects.create(user=user, name="아이템")

        resp = client.get(f"/collection/{item.id}/edit/")

        assert resp.status_code == 200
        assert "core/archive/collection_edit.html" in [t.name for t in resp.templates]


@pytest.mark.django_db
class TestOldCollectionRoutesRedirect:
    def test_구_컬렉션_목록_경로는_새_경로로_리다이렉트된다(self, client):
        resp = client.get("/archive/collection/")

        assert resp.status_code == 302
        assert resp.url == "/collection/"

    def test_구_컬렉션_목록_경로_리다이렉트는_쿼리스트링을_보존한다(self, client):
        resp = client.get("/archive/collection/?q=abc&is_wanted=true")

        assert resp.status_code == 302
        assert resp.url == "/collection/?q=abc&is_wanted=true"

    def test_구_컬렉션_등록_경로는_새_경로로_리다이렉트된다(self, client):
        resp = client.get("/archive/collection/new/")

        assert resp.status_code == 302
        assert resp.url == "/collection/new/"

    def test_구_컬렉션_수정_경로는_새_경로로_리다이렉트된다(self, client):
        resp = client.get("/archive/collection/1/edit/")

        assert resp.status_code == 302
        assert resp.url == "/collection/1/edit/"
