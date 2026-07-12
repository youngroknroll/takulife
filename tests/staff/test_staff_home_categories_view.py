"""staff.views.home_categories — /staff/home-categories/ (auth guard,
template assets, POST save, audit log).

Moved out of tests/events/test_home_featured_categories.py (2026-07-12):
that file mixed home-domain rendering tests (HomeConfig, "/" view) with
staff-route tests for this one view — pure relocation, no assertions
changed. HomeConfig/home-view coverage stays in tests/events/ (home
domain).
"""
import pytest
from django.db import IntegrityError
from django.test import Client

from core.models import HomeConfig
from staff.models import StaffActionLog


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
# D2. staff/home-categories — template assets (touch-target regression)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffHomeCategoriesTemplateAssets:
    """home_categories.html had no extra_css block, so staff_console.css
    never loaded — the checkbox/order-input touch targets rendered at raw UA
    defaults (checkbox ~13px, order input inline style="width: 4rem;")."""

    def test_response_loads_staff_console_css(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b"css/pages/staff_console.css" in resp.content

    def test_checkbox_is_wrapped_in_touch_target_label(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b'class="home-cat-select"' in resp.content
        assert b'class="home-cat-checkbox"' in resp.content

    def test_order_input_has_no_inline_style(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b'style="width: 4rem;"' not in resp.content

    def test_layout_uses_single_column_variant(self, staff_client):
        """staff_console.css now also loads on this page, which brings in
        dashboard.html's desktop 2-column .layout override (57.5rem+) — this
        page's .layout has only one .panel child (no side-stack), so at
        920px+ the panel gets squeezed into the 1.7fr column and the 0.9fr
        column renders empty. layout--single (archive_visit_create's
        single-panel convention) forces display:block regardless of
        viewport."""
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b'class="layout layout--single"' in resp.content


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
