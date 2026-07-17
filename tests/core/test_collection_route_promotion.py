"""IA-1 route promotion (target IA plan D1, .docs/plans/2026-07-16-target-ia-
plan.md §4): /collection/, /collection/new/, /collection/<id>/edit/ serve the
existing core.views.archive_collection_items /
archive_collection_item_create / archive_collection_item_edit views directly
(same view objects, only the route moved), and the old /archive/collection/*
paths 302-redirect to the new paths with the query string preserved.
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
