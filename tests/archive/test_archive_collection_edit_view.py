"""Tests for the collection-item edit page (core.views.archive_collection_item_edit).

Behavior under test (collection domain design plan §4 PR-C5b-2, CP-E1~E3, and
the create page's C8/C9 hidden-field guards mirrored here per the coach's
"create+edit" scope):
- /archive/collection/<id>/edit/ is owner-scoped: the owner gets a prefilled
  form, another user's item 404s (get_object_or_404(..., user=request.user)),
  and an anonymous request redirects to login.
- `visibility` and any `name="event"` control are never rendered, exactly as
  on the create page.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestArchiveCollectionEditView:
    def test_owner_gets_prefilled_edit_page(self, user_client, make_collection_item):
        user, client = user_client()
        item = make_collection_item(
            user,
            name="유메 아크릴",
            work_title="작품A",
            character_name="캐릭A",
            item_type="keyring",
            quantity=2,
            tradeable_quantity=1,
            is_wanted=True,
            memo="메모입니다",
        )

        resp = client.get(f"/archive/collection/{item.id}/edit/")

        assert resp.status_code == 200
        assert "core/archive/collection_edit.html" in [t.name for t in resp.templates]
        assert resp.context["item"] == item
        content = resp.content
        assert f'value="{item.name}"'.encode() in content
        assert f'value="{item.work_title}"'.encode() in content
        assert f'value="{item.character_name}"'.encode() in content

    def test_non_owner_item_returns_404(self, user_client, make_user, make_collection_item):
        owner = make_user()
        _, client = user_client()
        item = make_collection_item(owner, name="남의 아이템")

        resp = client.get(f"/archive/collection/{item.id}/edit/")

        assert resp.status_code == 404

    def test_anonymous_redirected_to_login(self, make_user, make_collection_item):
        owner = make_user()
        item = make_collection_item(owner, name="아이템")

        resp = Client().get(f"/archive/collection/{item.id}/edit/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionEditHiddenFields:
    def test_visibility_field_never_rendered(self, user_client, make_collection_item):
        user, client = user_client()
        item = make_collection_item(user, name="아이템")

        resp = client.get(f"/archive/collection/{item.id}/edit/")

        assert b'name="visibility"' not in resp.content

    def test_event_control_never_rendered(self, user_client, make_collection_item):
        user, client = user_client()
        item = make_collection_item(user, name="아이템")

        resp = client.get(f"/archive/collection/{item.id}/edit/")

        assert b'name="event"' not in resp.content
