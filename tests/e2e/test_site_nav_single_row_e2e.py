"""E2E: target IA plan §7-a-1 (.docs/plans/2026-07-16-target-ia-plan.md) —
mandatory gate. The header grew from 3 tabs to 4 (Home / Events / Collection
/ Activity) for the target IA; at 320px the 4 tabs must still share a single
row (no wrap onto a second line). The WED's approximation put the 4-tab sum
at ~245.5px against 288px available (safer than the prior 3-tab ~270.6px),
but the plan calls the real-viewport measurement a required gate rather than
trusting the approximation.

Updated for the shared-shell plan (.docs/plans/2026-07-20-shared-shell-plan.md
§D-1): at <=45rem the nav is now hidden behind a hamburger toggle
(button.nav-menu-toggle[data-nav-menu-toggle]) rather than always visible, so
the 320px case opens the panel first, then asserts the 4 links share a single
row. The desktop inline single-row assertion is preserved unchanged.
"""
import pytest

pytestmark = pytest.mark.e2e


class TestSiteNavSingleRowAt320px:
    def test_320px_뷰포트에서_햄버거를_열면_4개_탭이_한_줄에_배치된다(self, live_server, page, seed):
        page.set_viewport_size({"width": 320, "height": 740})
        page.goto(live_server.url + "/")

        page.locator("[data-nav-menu-toggle]").click()

        tops = page.evaluate(
            "() => Array.from(document.querySelectorAll('.site-nav a'))"
            ".map(a => Math.round(a.getBoundingClientRect().top))"
        )

        assert len(tops) == 4
        assert len(set(tops)) == 1


class TestSiteNavSingleRowOnDesktop:
    def test_데스크톱_뷰포트에서_4개_탭이_상시_한_줄에_배치된다(self, live_server, page, seed):
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(live_server.url + "/")

        tops = page.evaluate(
            "() => Array.from(document.querySelectorAll('.site-nav a'))"
            ".map(a => Math.round(a.getBoundingClientRect().top))"
        )

        assert len(tops) == 4
        assert len(set(tops)) == 1
