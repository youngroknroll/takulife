"""로그인 → 로그아웃 여정 — 보호 페이지 게이트가 실제 브라우저 세션에서
그대로 지켜지는지 확인한다(폼 로그인 성공 뒤 로그아웃, 재방문 시 재로그인 요구)."""
import re

from playwright.sync_api import expect

from tests.e2e.conftest import E2E_PASSWORD


def test_로그인한_사용자가_로그아웃하면_보호_페이지가_다시_로그인을_요구한다(
    page, base_url, verified_user, clear_cache_e2e
):
    user = verified_user(password=E2E_PASSWORD)

    page.goto(f"{base_url}/accounts/login/?next=/archive/")
    page.get_by_label("이메일").fill(user.email)
    page.get_by_label("비밀번호").fill(E2E_PASSWORD)
    page.get_by_role("button", name="로그인").click()

    expect(page).to_have_url(f"{base_url}/archive/")

    page.get_by_role("button", name="계정 메뉴").click()
    page.get_by_role("button", name="로그아웃").click()

    page.goto(f"{base_url}/archive/")
    expect(page).to_have_url(f"{base_url}/accounts/login/?next=/archive/")
