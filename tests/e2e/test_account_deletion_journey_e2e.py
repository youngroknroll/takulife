"""탈퇴를 요청하면 완료 페이지로 가고 같은 브라우저의 세션이 끊기는 여정."""
from playwright.sync_api import expect


def test_탈퇴를_요청하면_완료_페이지로_가고_세션이_끊긴다(
    page, base_url, verified_user, login_as, clear_cache_e2e, valid_password
):
    user = verified_user(password=valid_password)
    login_as(user)

    page.goto(f"{base_url}/accounts/delete/")
    page.get_by_label("현재 비밀번호로 확인").fill(valid_password)
    page.get_by_role("button", name="탈퇴").click()

    expect(page).to_have_url(f"{base_url}/accounts/delete/done/")
    expect(page.get_by_role("link", name="다시 로그인")).to_be_visible()

    page.goto(f"{base_url}/archive/")
    expect(page).to_have_url(f"{base_url}/accounts/login/?next=/archive/")

    user.refresh_from_db()
    assert user.deletion_requested_at is not None
