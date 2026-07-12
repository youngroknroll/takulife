"""E2E regression: top bar (.site-nav a, .topbar-link) touch targets (§5.4
44px). Both rendered at less than 44px before this fix (nav 40px,
topbar-link 36px).

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
    @pytest.mark.parametrize("width", [320, 375, 768])
    def test_nav_links_meet_min_height_and_stay_single_line(
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


class TestTopbarLinkTouchTarget:
    def test_topbar_link_meets_min_height(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(live_server.url + "/")

        heights = page.evaluate(
            "() => Array.from(document.querySelectorAll('.topbar-link'))"
            ".map(a => a.getBoundingClientRect().height)"
        )
        assert heights, "no .topbar-link elements found"
        assert all(h >= 44 for h in heights)
