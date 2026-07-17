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
from django.test import Client, override_settings

from core.models import HomeConfig
from staff.models import StaffActionLog


# ---------------------------------------------------------------------------
# D. staff/home-categories — auth guard
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffHomeCategoriesAuth:
    pytestmark = pytest.mark.web

    def test_비로그인_사용자가_홈_카테고리_설정_화면에_접근하면_302로_리다이렉트된다(self):
        resp = Client().get("/staff/home-categories/")

        assert resp.status_code == 302

    def test_일반_사용자가_홈_카테고리_설정_화면에_접근하면_403이_응답된다(self, make_user):
        user = make_user()
        client = Client()
        client.force_login(user)

        resp = client.get("/staff/home-categories/")

        assert resp.status_code == 403

    def test_스태프가_홈_카테고리_설정_화면에_접근하면_200이_응답된다(self, staff_client):
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

    pytestmark = pytest.mark.web

    def test_홈_카테고리_설정_화면은_staff_console_css를_로드한다(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b"css/pages/staff_console.css" in resp.content

    def test_홈_카테고리_설정_화면의_체크박스는_터치_타깃_라벨로_감싸져_있다(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b'class="home-cat-select"' in resp.content
        assert b'class="home-cat-checkbox"' in resp.content

    def test_홈_카테고리_설정_화면의_순서_입력_필드는_인라인_스타일을_갖지_않는다(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b'style="width: 4rem;"' not in resp.content

    def test_홈_카테고리_설정_화면은_단일_컬럼_레이아웃_변형을_사용한다(self, staff_client):
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
    pytestmark = pytest.mark.web

    def test_강조_카테고리를_저장하면_지정한_순서대로_저장된다(self, staff_client):
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

    def test_강조_카테고리_저장시_순서_필드_값을_기준으로_정렬해_저장한다(self, staff_client):
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

    def test_존재하지_않는_슬러그로_저장을_시도하면_무시되고_유효한_카테고리만_저장된다(self, staff_client):
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

    def test_순서_값이_숫자가_아니면_오류_없이_안전하게_저장된다(self, staff_client):
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
    pytestmark = pytest.mark.contract

    def test_강조_카테고리를_저장하면_감사_로그가_정확히_한_건_기록된다(self, staff_client):
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

    def test_홈_카테고리_설정_화면을_조회만_하면_감사_로그가_기록되지_않는다(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert resp.status_code == 200
        assert StaffActionLog.objects.count() == 0

    def test_감사_로그_기록이_실패하면_설정_변경도_함께_롤백된다(self, staff_client, monkeypatch):
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

    def test_신뢰할_프록시_설정이_없으면_전달된_X_Forwarded_For_헤더를_무시하고_원격_주소를_사용한다(self, staff_client):
        """Spoofing guard: TRUSTED_PROXY_COUNT unset (the default) must not
        let an untrusted X-Forwarded-For header override REMOTE_ADDR."""
        staff, client = staff_client()

        resp = client.post(
            "/staff/home-categories/",
            data={
                "feature_exhibition": "on",
                "order_exhibition": "1",
            },
            REMOTE_ADDR="203.0.113.9",
            HTTP_X_FORWARDED_FOR="198.51.100.1",
        )

        assert resp.status_code == 302
        entry = StaffActionLog.objects.get()
        assert entry.ip_address == "203.0.113.9"

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_신뢰할_프록시_설정이_있으면_전달된_X_Forwarded_For_헤더에서_클라이언트_IP를_해석한다(self, staff_client):
        staff, client = staff_client()

        resp = client.post(
            "/staff/home-categories/",
            data={
                "feature_exhibition": "on",
                "order_exhibition": "1",
            },
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_FORWARDED_FOR="203.0.113.9",
        )

        assert resp.status_code == 302
        entry = StaffActionLog.objects.get()
        assert entry.ip_address == "203.0.113.9"
