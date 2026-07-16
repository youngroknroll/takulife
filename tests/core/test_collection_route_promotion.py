"""IA-1 route promotion (target IA plan D1, .docs/plans/2026-07-16-target-ia-
plan.md §4): /collection/, /collection/new/, /collection/<id>/edit/ serve the
existing core.views.archive_collection_items /
archive_collection_item_create / archive_collection_item_edit views directly
(same view objects, only the route moved), and the old /archive/collection/*
paths 302-redirect to the new paths with the query string preserved.
"""
import pytest

from archive.models import CollectionItem


@pytest.mark.django_db
class TestCollectionRoutesPromoted:
    def test_collection_list_route_serves_existing_view(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/")

        assert resp.status_code == 200
        assert "core/archive/collection.html" in [t.name for t in resp.templates]

    def test_collection_create_route_serves_existing_view(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")

        assert resp.status_code == 200
        assert "core/archive/collection_create.html" in [t.name for t in resp.templates]

    def test_collection_edit_route_serves_existing_view(self, user_client):
        user, client = user_client()
        item = CollectionItem.objects.create(user=user, name="아이템")

        resp = client.get(f"/collection/{item.id}/edit/")

        assert resp.status_code == 200
        assert "core/archive/collection_edit.html" in [t.name for t in resp.templates]


@pytest.mark.django_db
class TestOldCollectionRoutesRedirect:
    def test_old_collection_list_url_redirects_to_new_path(self, client):
        resp = client.get("/archive/collection/")

        assert resp.status_code == 302
        assert resp.url == "/collection/"

    def test_old_collection_list_url_preserves_query_string(self, client):
        resp = client.get("/archive/collection/?q=abc&is_wanted=true")

        assert resp.status_code == 302
        assert resp.url == "/collection/?q=abc&is_wanted=true"

    def test_old_collection_create_url_redirects_to_new_path(self, client):
        resp = client.get("/archive/collection/new/")

        assert resp.status_code == 302
        assert resp.url == "/collection/new/"

    def test_old_collection_edit_url_redirects_to_new_path(self, client):
        resp = client.get("/archive/collection/1/edit/")

        assert resp.status_code == 302
        assert resp.url == "/collection/1/edit/"
