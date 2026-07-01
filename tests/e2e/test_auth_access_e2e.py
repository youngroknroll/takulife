"""E2E: authentication and staff access control across real navigations."""
import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


class TestAuth:
    def test_login_with_wrong_password_stays_and_shows_error(
        self, live_server, page, seed
    ):
        page.goto(f"{live_server.url}/accounts/login/?next=/")
        page.fill('input[name="login"]', "e2e_user@example.com")
        page.fill('input[name="password"]', "wrong-password")
        page.click('button[type="submit"]')

        # Stays on the login page (no redirect to next) and re-renders the form.
        expect(page).to_have_url(re.compile(r"/accounts/login/"))
        expect(page.locator(".auth-error")).to_be_visible()

    def test_login_success_redirects_to_next(self, live_server, page, seed, login):
        page.goto(f"{live_server.url}/accounts/login/?next=/archive/")
        page.fill('input[name="login"]', "e2e_user@example.com")
        page.fill('input[name="password"]', seed.password)
        page.click('button[type="submit"]')

        expect(page).to_have_url(f"{live_server.url}/archive/")
        # Topbar reflects the logged-in user.
        expect(page.locator("body")).to_contain_text("e2e_user@example.com")


class TestStaffAccessControl:
    def test_regular_user_blocked_from_drafts(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)

        page.goto(f"{live_server.url}/event-drafts/")

        # staff_member_required bounces a non-staff user to the admin login.
        expect(page).to_have_url(re.compile(r"/admin/login/.*next=/event-drafts/"))

    def test_regular_user_blocked_from_home_categories(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)

        page.goto(f"{live_server.url}/staff/home-categories/")

        expect(page).to_have_url(re.compile(r"/admin/login/"))

    def test_staff_user_can_open_drafts(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)

        page.goto(f"{live_server.url}/event-drafts/")

        expect(page).to_have_url(f"{live_server.url}/event-drafts/")
        expect(page.locator("h1")).to_contain_text("드래프트 관리")

    def test_staff_user_can_open_home_categories(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)

        page.goto(f"{live_server.url}/staff/home-categories/")

        expect(page).to_have_url(f"{live_server.url}/staff/home-categories/")
        expect(page.locator("h1")).to_contain_text("홈 카테고리 설정")
