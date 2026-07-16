"""E2E: target IA plan D4 (.docs/plans/2026-07-16-target-ia-plan.md §7-b-6)
— a login with no explicit ``?next=`` lands on /collection/, with the
Collection tab shown active. The shared tests/e2e/conftest.py ``login``
helper always drives the form through ``?next=/archive/statuses/``, so this
flow submits the login form directly instead.
"""
import pytest

pytestmark = pytest.mark.e2e


class TestLoginRedirectLanding:
    def test_login_without_next_lands_on_collection(self, live_server, page, seed):
        page.goto(f"{live_server.url}/accounts/login/")
        page.fill('input[name="login"]', seed.user.email)
        page.fill('input[name="password"]', seed.password)
        page.click('button[type="submit"]')

        page.wait_for_url(f"{live_server.url}/collection/")
        assert page.locator("h1").inner_text() == "내 컬렉션"
        assert page.locator('.site-nav a[href="/collection/"]').get_attribute("class") == "active"
