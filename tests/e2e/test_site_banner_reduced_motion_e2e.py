"""E2E: site notice banner (.site-banner) marquee under
prefers-reduced-motion — shared-shell plan
(.docs/plans/2026-07-20-shared-shell-plan.md §D-4, acceptance criterion 3).

Follows test_confirm_modal_reduced_motion_e2e.py's browser_context_args
override convention (line 30-32) to force reduced_motion: reduce, then
asserts the .marquee-track loses its animation entirely (site-chrome.css:
`prefers-reduced-motion: reduce` -> `animation: none !important`). The
default-motion counterpart asserts the marquee keeps a real animation name
running (the CSS's baseline `@keyframes marquee` — not "none"), mirroring
TestConfirmModalDefaultMotion's regression-guard pattern for the
non-reduced-motion path.
"""
import pytest

pytestmark = pytest.mark.e2e

TRACK = ".marquee-track"


class TestSiteBannerReducedMotion:
    @pytest.fixture
    def browser_context_args(self, browser_context_args):
        return {**browser_context_args, "reduced_motion": "reduce"}

    def test_reduced_motion에서_공지_배너_마퀴는_애니메이션이_제거된다(self, live_server, page, seed):
        page.goto(live_server.url + "/")

        animation_name = page.evaluate(
            f"() => getComputedStyle(document.querySelector('{TRACK}')).animationName"
        )
        assert animation_name == "none"


class TestSiteBannerDefaultMotion:
    def test_reduced_motion이_아니면_공지_배너_마퀴는_애니메이션을_유지한다(self, live_server, page, seed):
        page.goto(live_server.url + "/")

        animation_name = page.evaluate(
            f"() => getComputedStyle(document.querySelector('{TRACK}')).animationName"
        )
        assert animation_name != "none"
