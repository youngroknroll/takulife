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

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveCollectionEditView:
    def test_소유자가_수정_페이지에_접근하면_기존_값이_채워진_폼이_표시된다(self, user_client, make_collection_item):
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

        resp = client.get(f"/collection/{item.id}/edit/")

        assert resp.status_code == 200
        assert "core/archive/collection_edit.html" in [t.name for t in resp.templates]
        assert resp.context["item"] == item
        content = resp.content
        assert f'value="{item.name}"'.encode() in content
        assert f'value="{item.work_title}"'.encode() in content
        assert f'value="{item.character_name}"'.encode() in content

    def test_타인_소유_항목의_수정_페이지에_접근하면_404가_된다(self, user_client, make_user, make_collection_item):
        owner = make_user()
        _, client = user_client()
        item = make_collection_item(owner, name="남의 아이템")

        resp = client.get(f"/collection/{item.id}/edit/")

        assert resp.status_code == 404

    def test_비로그인_사용자가_수정_페이지에_접근하면_로그인_페이지로_리다이렉트된다(self, make_user, make_collection_item):
        owner = make_user()
        item = make_collection_item(owner, name="아이템")

        resp = Client().get(f"/collection/{item.id}/edit/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionEditHiddenFields:
    def test_수정_페이지에는_visibility_필드가_렌더링되지_않는다(self, user_client, make_collection_item):
        user, client = user_client()
        item = make_collection_item(user, name="아이템")

        resp = client.get(f"/collection/{item.id}/edit/")

        assert b'name="visibility"' not in resp.content

    def test_수정_페이지에는_이벤트_선택_컨트롤이_렌더링되지_않는다(self, user_client, make_collection_item):
        user, client = user_client()
        item = make_collection_item(user, name="아이템")

        resp = client.get(f"/collection/{item.id}/edit/")

        assert b'name="event"' not in resp.content
