"""Tests for HomeConfig featured categories and staff management route.

Covers:
- HomeConfig.get_solo: singleton semantics (pk=1, idempotent)
- HomeConfig.featured_category_pairs: fallback (all 6), filtered, ordered
- home view: category_tiles backward compat and config-aware rendering
- staff/home-categories: auth guard, GET 200, POST save, vocab validation
"""
import pytest
from django.db import IntegrityError
from django.test import Client

from core.models import HomeConfig
from core.vocab import CATEGORY, CATEGORY_LABELS
from staff.models import StaffActionLog


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


# ---------------------------------------------------------------------------
# D. staff/home-categories — auth guard
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffHomeCategoriesAuth:
    def test_anonymous_redirected(self):
        resp = Client().get("/staff/home-categories/")

        assert resp.status_code == 302

    def test_regular_user_redirected(self, make_user):
        user = make_user()
        client = Client()
        client.force_login(user)

        resp = client.get("/staff/home-categories/")

        assert resp.status_code == 403

    def test_staff_user_gets_200(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# E. staff/home-categories — POST (PRG)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffHomeCategoriesPost:
    def test_post_saves_featured_categories_in_order(self, staff_client):
        _, client = staff_client()

        resp = client.post(
            "/staff/home-categories/",
            data={
                "feature_exhibition": "on",
                "order_exhibition": "1",
                "feature_popup_store": "on",
                "order_popup_store": "2",
            },
        )

        assert resp.status_code == 302
        config = HomeConfig.get_solo()
        assert config.featured_categories == ["exhibition", "popup_store"]

    def test_post_respects_order_field(self, staff_client):
        """order_<slug> fields determine the sort; popup_store first here."""
        _, client = staff_client()

        resp = client.post(
            "/staff/home-categories/",
            data={
                "feature_exhibition": "on",
                "order_exhibition": "2",
                "feature_popup_store": "on",
                "order_popup_store": "1",
            },
        )

        assert resp.status_code == 302
        config = HomeConfig.get_solo()
        assert config.featured_categories == ["popup_store", "exhibition"]

    def test_post_bogus_slug_in_form_data_ignored(self, staff_client):
        """Crafted feature_<bogus> POST fields must not reach saved config."""
        _, client = staff_client()

        resp = client.post(
            "/staff/home-categories/",
            data={
                "feature_bogus_slug": "on",
                "order_bogus_slug": "1",
                "feature_exhibition": "on",
                "order_exhibition": "2",
            },
        )

        assert resp.status_code == 302
        config = HomeConfig.get_solo()
        assert "bogus_slug" not in config.featured_categories
        assert config.featured_categories == ["exhibition"]

    def test_post_invalid_order_falls_back_safely(self, staff_client):
        """Non-integer order_<slug> must not raise 500."""
        _, client = staff_client()

        resp = client.post(
            "/staff/home-categories/",
            data={
                "feature_exhibition": "on",
                "order_exhibition": "not-a-number",
            },
        )

        assert resp.status_code == 302
        config = HomeConfig.get_solo()
        assert "exhibition" in config.featured_categories


# ---------------------------------------------------------------------------
# F. staff/home-categories — audit log (PR-3)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffHomeCategoriesAuditLog:
    def test_post_writes_single_home_categories_log_entry(self, staff_client):
        staff, client = staff_client()

        resp = client.post(
            "/staff/home-categories/",
            data={
                "feature_exhibition": "on",
                "order_exhibition": "1",
            },
            REMOTE_ADDR="203.0.113.9",
            HTTP_USER_AGENT="pytest/1.0",
        )

        assert resp.status_code == 302
        assert StaffActionLog.objects.count() == 1
        entry = StaffActionLog.objects.get()
        assert entry.action == StaffActionLog.Action.HOME_CATEGORIES
        assert entry.actor_id == staff.id
        assert entry.target_draft is None
        assert entry.ip_address == "203.0.113.9"
        assert entry.user_agent == "pytest/1.0"

    def test_get_writes_no_log(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert resp.status_code == 200
        assert StaffActionLog.objects.count() == 0

    def test_post_rolls_back_config_when_audit_log_write_fails(self, staff_client, monkeypatch):
        staff, client = staff_client()
        original_categories = list(HomeConfig.get_solo().featured_categories)

        def fail_log_create(*args, **kwargs):
            raise IntegrityError("simulated log write failure")

        monkeypatch.setattr("staff.views.StaffActionLog.objects.create", fail_log_create)
        client.raise_request_exception = False

        resp = client.post(
            "/staff/home-categories/",
            data={
                "feature_popup_store": "on",
                "order_popup_store": "1",
            },
        )

        assert resp.status_code == 500
        config = HomeConfig.get_solo()
        assert config.featured_categories == original_categories
        assert StaffActionLog.objects.count() == 0
