"""홈 카테고리 설정 화면(/staff/home-categories/) 인증 게이트, 템플릿 자산, 저장, 감사 로그 검증."""
import pytest
from django.db import IntegrityError
from django.test import Client, override_settings

from core.models import HomeConfig
from staff.models import StaffActionLog


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


@pytest.mark.django_db
class TestStaffHomeCategoriesTemplateAssets:
    """전용 스태프 CSS가 빠지면 체크박스·순서 입력의 터치 타깃이 브라우저 기본 크기로 작아진다."""

    pytestmark = pytest.mark.web

    def test_홈_카테고리_설정_화면은_전용_staff_css를_로드한다(self, staff_client):
        """스태프 콘솔 재설계(D2·D3)로 소비자 CSS 의존이 끊기고 페이지 전용
        스태프 CSS(`css/staff/pages/home_categories.css`)로 대체됐다 — 터치
        타깃 크기는 이제 이 파일이 책임진다."""
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b"css/staff/pages/home_categories.css" in resp.content

    def test_홈_카테고리_설정_화면의_체크박스는_터치_타깃_라벨로_감싸져_있다(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b'class="home-cats-toggle"' in resp.content
        assert b'class="home-cats-checkbox"' in resp.content

    def test_홈_카테고리_설정_화면의_순서_입력_필드는_인라인_스타일을_갖지_않는다(self, staff_client):
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")

        assert b'style="width: 4rem;"' not in resp.content

    def test_홈_카테고리_설정_화면은_미리보기_레일이_있는_2단_레이아웃을_쓴다(self, staff_client):
        """재설계 전에는 패널이 하나뿐이라 2단 그리드를 쓰면 빈 컬럼이 남았고,
        그래서 layout--single로 강제 단일 컬럼 처리했다. 새 화면은 두 번째
        컬럼에 실제 콘텐츠(홈 미리보기 레일)를 채워 빈 컬럼 문제 자체가
        구조적으로 없다 — 전용 grid(home-cats-grid)가 항상 두 패널을 보여준다."""
        _, client = staff_client()

        resp = client.get("/staff/home-categories/")
        content = resp.content.decode()

        assert 'class="home-cats-grid"' in content
        assert 'class="home-cats-panel"' in content
        assert 'class="home-cats-rail"' in content


@pytest.mark.django_db
class TestStaffHomeCategoriesEventCounts:
    """B6: 카테고리별 게시된 이벤트 수를 함께 보여준다."""

    pytestmark = pytest.mark.web

    def test_카테고리별_행에_게시된_이벤트_수가_붙는다(self, staff_client, make_event):
        make_event(category="exhibition", official_url="https://example.com/home-cat-1")
        make_event(category="exhibition", official_url="https://example.com/home-cat-2")
        make_event(category="popup_store", official_url="https://example.com/home-cat-3")

        _, client = staff_client()
        resp = client.get("/staff/home-categories/")

        rows_by_slug = {row["slug"]: row for row in resp.context["category_rows"]}
        assert rows_by_slug["exhibition"]["event_count"] == 2
        assert rows_by_slug["popup_store"]["event_count"] == 1

    def test_이벤트가_없는_카테고리는_0건으로_표시된다(self, staff_client):
        _, client = staff_client()
        resp = client.get("/staff/home-categories/")

        rows_by_slug = {row["slug"]: row for row in resp.context["category_rows"]}
        assert rows_by_slug["exhibition"]["event_count"] == 0

    def test_게시되지_않은_초안_이벤트는_카테고리_건수에_포함되지_않는다(self, staff_client, make_draft_event):
        make_draft_event(category="exhibition", official_url="https://example.com/home-cat-draft")

        _, client = staff_client()
        resp = client.get("/staff/home-categories/")

        rows_by_slug = {row["slug"]: row for row in resp.context["category_rows"]}
        assert rows_by_slug["exhibition"]["event_count"] == 0


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
        """조작된 필드로 존재하지 않는 슬러그를 보내도 저장된 설정에 반영되면 안 된다."""
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
        """신뢰 프록시 설정이 없을 때는 X-Forwarded-For를 신뢰하면 IP가 위조될 수 있어 무시해야 한다."""
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
