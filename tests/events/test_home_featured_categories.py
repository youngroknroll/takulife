"""Tests for HomeConfig featured categories and the home view's rendering.

Covers:
- HomeConfig.get_solo: singleton semantics (pk=1, idempotent)
- HomeConfig.featured_category_pairs: fallback (all 6), filtered, ordered
- home view: category_tiles backward compat and config-aware rendering

staff/home-categories route tests (auth guard, template assets, POST,
audit log) moved to tests/staff/test_staff_home_categories_view.py
(2026-07-12) — this file now covers only the home domain.
"""
import pytest
from django.test import Client

from core.models import HomeConfig
from core.vocab import CATEGORY


# ---------------------------------------------------------------------------
# A. HomeConfig singleton
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHomeConfigSingleton:
    pytestmark = pytest.mark.domain

    def test_HomeConfig를_처음_조회하면_pk_1인_싱글턴_행이_반환된다(self):
        config = HomeConfig.get_solo()

        assert config.pk == 1

    def test_HomeConfig를_반복_조회해도_같은_pk의_싱글턴_행이_반환된다(self):
        first = HomeConfig.get_solo()
        second = HomeConfig.get_solo()

        assert first.pk == second.pk


# ---------------------------------------------------------------------------
# B. featured_category_pairs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFeaturedCategoryPairs:
    pytestmark = pytest.mark.domain

    def test_강조_카테고리가_비어있으면_전체_어휘_카테고리를_원래_순서대로_반환한다(self):
        config = HomeConfig.get_solo()
        config.featured_categories = []
        config.save()

        pairs = config.featured_category_pairs()

        assert pairs == list(CATEGORY)

    def test_강조_카테고리를_지정하면_저장된_순서대로_해당_카테고리만_반환한다(self):
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        pairs = config.featured_category_pairs()

        assert pairs == [("exhibition", "전시"), ("popup_store", "팝업스토어")]

    def test_강조_카테고리에_존재하지_않는_슬러그가_있으면_걸러내고_나머지만_반환한다(self):
        config = HomeConfig.get_solo()
        config.featured_categories = ["bogus", "exhibition"]
        config.save()

        pairs = config.featured_category_pairs()

        slugs = [s for s, _ in pairs]
        assert "bogus" not in slugs
        assert "exhibition" in slugs
        assert len(slugs) == 1


# ---------------------------------------------------------------------------
# C. home view — category_tiles integration
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHomeViewCategoryTilesIntegration:
    pytestmark = pytest.mark.web

    def test_HomeConfig_행이_없으면_홈_화면에_전체_6개_카테고리_타일이_어휘_순서대로_노출된다(self):
        """Backward compat: no HomeConfig row → all 6 categories."""
        resp = Client().get("/")

        assert resp.status_code == 200
        slugs = [t["slug"] for t in resp.context["category_tiles"]]
        assert slugs == [s for s, _ in CATEGORY]
        assert len(slugs) == 6

    def test_HomeConfig_행이_없고_행사가_없으면_모든_카테고리_타일의_건수가_0이다(self):
        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        for slug, _ in CATEGORY:
            assert tiles[slug]["count"] == 0

    def test_HomeConfig에_강조_카테고리를_설정하면_홈_화면에_선택한_카테고리_타일만_순서대로_노출된다(self):
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        resp = Client().get("/")

        slugs = [t["slug"] for t in resp.context["category_tiles"]]
        assert slugs == ["exhibition", "popup_store"]

    def test_강조_카테고리_설정_시_각_타일에_해당_카테고리_행사_건수가_정확히_반영된다(self, make_event):
        make_event(category="exhibition")
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["exhibition"]["count"] == 1
        assert tiles["popup_store"]["count"] == 0

    def test_카테고리_타일은_slug_label_count_필드를_항상_포함한다(self):
        """category_tiles always carry {slug, label, count} — template contract."""
        resp = Client().get("/")

        for tile in resp.context["category_tiles"]:
            assert "slug" in tile
            assert "label" in tile
            assert "count" in tile
