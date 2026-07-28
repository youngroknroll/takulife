"""Tests for the 비공식 장소 등록 create page (core.views.archive_personal_entry_create).

Behavior under test (직접 등록 에디토리얼 plan Part 1 §3, PV-1/PV-2):
- /archive/personal/new/ is login-gated (mirrors archive_collection_item_create).
- The page render-only — it posts to the existing /api/personal-entries/ JSON
  API, no new API is introduced here.
- Context carries PERSONAL_ENTRY_CATEGORY_SUGGESTIONS (free-input hint chips,
  not a `choices` constraint) so the template can render the category
  suggestion chips.
"""
import uuid

import pytest

from core.vocab import PERSONAL_ENTRY_CATEGORY_SUGGESTIONS

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchivePersonalEntryCreateViewAuth:
    def test_로그인한_사용자가_비공식_장소_등록_페이지에_접근하면_카테고리_추천_컨텍스트와_함께_렌더링된다(
        self, user_client
    ):
        _, client = user_client()

        resp = client.get("/archive/personal/new/")

        assert resp.status_code == 200
        assert "core/archive/personal_create.html" in [t.name for t in resp.templates]
        assert resp.context["PERSONAL_ENTRY_CATEGORY_SUGGESTIONS"] == PERSONAL_ENTRY_CATEGORY_SUGGESTIONS
        assert len(resp.context["PERSONAL_ENTRY_CATEGORY_SUGGESTIONS"]) == 6

    def test_비공식_장소_등록_페이지는_렌더마다_발급된_클라이언트_토큰을_컨텍스트와_히든_인풋에_담는다(
        self, user_client
    ):
        """bfcache duplicate-creation track (INTG-BE-05-PE-SSR): mirrors
        archive_visit_create/archive_collection_item_create's per-render
        client_token issuance (core/views.py:1409-1421, :1761-1772) so the
        form survives a bfcache DOM snapshot and can dedupe a replayed
        submission (plan §4-1)."""
        _, client = user_client()

        resp = client.get("/archive/personal/new/")

        assert resp.status_code == 200
        token = resp.context["client_token"]
        assert uuid.UUID(str(token))
        assert (
            f'name="client_token" value="{token}"' in resp.content.decode()
        )

    def test_비로그인_사용자가_비공식_장소_등록_페이지에_접근하면_로그인으로_리다이렉트된다(self, client):
        resp = client.get("/archive/personal/new/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchivePersonalEntriesLegacyRedirect:
    def test_구_items_경로는_personal_목록으로_리다이렉트된다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/items/")

        assert resp.status_code in (301, 302)
        assert resp.url == "/archive/personal/"
