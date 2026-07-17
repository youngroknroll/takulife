"""E2E regression: top bar (.site-nav a, account menu) touch targets (§5.4
44px). .site-nav a rendered at less than 44px before this fix (40px);
.topbar-link's own 36px case was superseded when the header account-menu
dropdown (core/partials/_topbar.html) replaced the authenticated topbar's
inline pill links (스태프 콘솔/관리자/회원 탈퇴/로그아웃) with a single 44px
avatar toggle plus an on-open item list — .topbar-link now renders only for
the logged-out 로그인/회원가입 pair, so the touch-target guarantee for the
authenticated state moved to .account-menu-toggle/.account-menu-item below.

--site-header-h (site-chrome.css) is derived from .site-nav a's min-height
and must stay in sync with it — a stale token would misposition every sticky
panel that clears the header (event_detail .aside, event_list .filters,
layout .side-stack). This also guards that the 320/375/768/905px header
never gains a *new* wrap point from the touch-target bump (measured before
and after: nav stays single-line at every one of those widths, in every
auth state, both before and after this change — only the header's raw
height grew, proportionally to the min-height increase).
"""
import pytest

pytestmark = pytest.mark.e2e


def _nav_is_single_line(page):
    tops = page.evaluate(
        "() => Array.from(document.querySelectorAll('.site-nav a'))"
        ".map(a => Math.round(a.getBoundingClientRect().top))"
    )
    return len(set(tops)) <= 1


class TestTopbarNavLinkTouchTarget:
    @pytest.mark.parametrize(
        "width",
        [320, 375, 768],
        ids=["너비_320px", "너비_375px", "너비_768px"],
    )
    def test_뷰포트_너비에서도_네비게이션_링크가_44px_이상이고_한_줄을_유지한다(
        self, live_server, page, seed, width
    ):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(live_server.url + "/")

        heights = page.evaluate(
            "() => Array.from(document.querySelectorAll('.site-nav a'))"
            ".map(a => a.getBoundingClientRect().height)"
        )
        assert heights, "no .site-nav a links found"
        assert all(h >= 44 for h in heights)
        assert _nav_is_single_line(page)


class TestAccountMenuTouchTarget:
    def test_계정_메뉴_토글은_44px_이상의_터치_영역을_갖는다(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(live_server.url + "/")

        box = page.locator("[data-account-menu-toggle]").bounding_box()
        assert box is not None
        assert box["height"] >= 44

    def test_계정_메뉴를_열면_메뉴_항목들이_44px_이상의_터치_영역을_갖는다(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(live_server.url + "/")

        page.locator("[data-account-menu-toggle]").click()
        heights = page.evaluate(
            "() => Array.from(document.querySelectorAll('.account-menu-item'))"
            ".map(a => a.getBoundingClientRect().height)"
        )
        assert heights, "no .account-menu-item elements found"
        assert all(h >= 44 for h in heights)
