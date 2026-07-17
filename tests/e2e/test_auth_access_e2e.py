"""E2E: authentication and staff access control across real navigations."""
import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


class TestAuth:
    def test_잘못된_비밀번호로_로그인하면_로그인_페이지에_머무르며_오류를_보여준다(
        self, live_server, page, seed
    ):
        page.goto(f"{live_server.url}/accounts/login/?next=/")
        page.fill('input[name="login"]', "e2e_user@example.com")
        page.fill('input[name="password"]', "wrong-password")
        page.click('button[type="submit"]')

        # Stays on the login page (no redirect to next) and re-renders the form.
        expect(page).to_have_url(re.compile(r"/accounts/login/"))
        expect(page.locator(".auth-error")).to_contain_text(
            "이메일 또는 비밀번호가 올바르지 않습니다"
        )

    def test_로그인에_성공하면_next_파라미터로_리다이렉트된다(self, live_server, page, seed, login):
        page.goto(f"{live_server.url}/accounts/login/?next=/archive/")
        page.fill('input[name="login"]', "e2e_user@example.com")
        page.fill('input[name="password"]', seed.password)
        page.click('button[type="submit"]')

        expect(page).to_have_url(f"{live_server.url}/archive/")
        # Topbar reflects the logged-in user.
        expect(page.locator("body")).to_contain_text("e2e_user@example.com")


class TestStaffAccessControl:
    def test_일반_사용자는_드래프트_관리_페이지_접근이_차단된다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)

        # staff_console_required raises PermissionDenied (403) for an
        # authenticated non-staff user — it must not bounce back to login.
        resp = page.goto(f"{live_server.url}/staff/drafts/")

        assert resp.status == 403

    def test_일반_사용자는_홈_카테고리_설정_페이지_접근이_차단된다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)

        resp = page.goto(f"{live_server.url}/staff/home-categories/")

        assert resp.status == 403

    def test_스태프_사용자는_드래프트_관리_페이지를_열_수_있다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)

        page.goto(f"{live_server.url}/staff/drafts/")

        expect(page).to_have_url(f"{live_server.url}/staff/drafts/")
        expect(page.locator("h1")).to_contain_text("드래프트 관리")

    def test_스태프_사용자는_홈_카테고리_설정_페이지를_열_수_있다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)

        page.goto(f"{live_server.url}/staff/home-categories/")

        expect(page).to_have_url(f"{live_server.url}/staff/home-categories/")
        expect(page.locator("h1")).to_contain_text("홈 카테고리 설정")
