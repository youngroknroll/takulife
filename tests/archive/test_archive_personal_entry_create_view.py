"""비공식 장소 등록 페이지(core.views.archive_personal_entry_create) 테스트.

검증 대상 (직접 등록 에디토리얼 plan Part 1 §3, PV-1/PV-2): /archive/personal/new/는
로그인 게이트가 걸려 있고(archive_collection_item_create와 동일한 패턴),
페이지는 렌더링만 담당하며 기존 /api/personal-entries/ JSON API로 제출한다
(새 API는 도입하지 않는다). 컨텍스트에는 PERSONAL_ENTRY_CATEGORY_SUGGESTIONS
(자유 입력용 힌트 칩이며 `choices` 제약이 아님)가 담겨 템플릿이 카테고리
추천 칩을 렌더링할 수 있다.
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
        """bfcache 중복 생성 트랙(INTG-BE-05-PE-SSR): archive_visit_create /
        archive_collection_item_create의 렌더마다 client_token 발급 패턴
        (core/views.py:1409-1421, :1761-1772)을 그대로 따라, 폼이 bfcache DOM
        스냅샷에서도 살아남고 재전송된 제출을 중복 제거할 수 있게 한다(plan §4-1)."""
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
