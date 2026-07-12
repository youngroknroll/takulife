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
from core.vocab import CATEGORY, CATEGORY_LABELS


# ---------------------------------------------------------------------------
# A. HomeConfig singleton
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHomeConfigSingleton:
    def test_get_solo_returns_pk1(self):
        config = HomeConfig.get_solo()

        assert config.pk == 1

    def test_get_solo_second_call_returns_same_pk(self):
        first = HomeConfig.get_solo()
        second = HomeConfig.get_solo()

        assert first.pk == second.pk


# ---------------------------------------------------------------------------
# B. featured_category_pairs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFeaturedCategoryPairs:
    def test_empty_featured_returns_all_vocab_in_order(self):
        config = HomeConfig.get_solo()
        config.featured_categories = []
        config.save()

        pairs = config.featured_category_pairs()

        assert pairs == list(CATEGORY)

    def test_set_categories_returns_only_those_in_stored_order(self):
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        pairs = config.featured_category_pairs()

        assert pairs == [("exhibition", "전시"), ("popup_store", "팝업스토어")]

    def test_bogus_slug_filtered_out(self):
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
    def test_no_config_produces_six_tiles_in_vocab_order(self):
        """Backward compat: no HomeConfig row → all 6 categories."""
        resp = Client().get("/")

        assert resp.status_code == 200
        slugs = [t["slug"] for t in resp.context["category_tiles"]]
        assert slugs == [s for s, _ in CATEGORY]
        assert len(slugs) == 6

    def test_no_config_tiles_carry_count_zero_when_no_events(self):
        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        for slug, _ in CATEGORY:
            assert tiles[slug]["count"] == 0

    def test_config_set_produces_only_selected_tiles_in_order(self):
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        resp = Client().get("/")

        slugs = [t["slug"] for t in resp.context["category_tiles"]]
        assert slugs == ["exhibition", "popup_store"]

    def test_config_set_attaches_correct_count(self, make_event):
        make_event(category="exhibition")
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["exhibition"]["count"] == 1
        assert tiles["popup_store"]["count"] == 0

    def test_tiles_carry_label_field(self):
        """category_tiles always carry {slug, label, count} — template contract."""
        resp = Client().get("/")

        for tile in resp.context["category_tiles"]:
            assert "slug" in tile
            assert "label" in tile
            assert "count" in tile
