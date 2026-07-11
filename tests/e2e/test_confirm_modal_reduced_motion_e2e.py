"""E2E regression: confirm-modal.js under prefers-reduced-motion.

close() used to wait on a transitionend event before restoring [hidden], but
confirm-modal.css :87 strips the transition entirely under
prefers-reduced-motion, so transitionend never fires — the overlay stayed
rendered (opacity:0; pointer-events:auto; z-index:1000), silently absorbing
every click on the page behind it. confirm-modal.js is loaded globally from
base.html, so any public page exercises it.
"""
import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

OVERLAY = ".confirm-overlay"


def _open_and_dismiss(page, live_server):
    page.goto(live_server.url + "/")
    # Not awaited on purpose: TakuConfirm's promise only resolves once 아니오
    # is clicked below, and blocking here would deadlock the test.
    page.evaluate("() => { window.TakuConfirm('테스트'); }")
    expect(page.locator(OVERLAY)).to_have_class(re.compile(r"is-open"))
    page.click(".confirm-no")


class TestConfirmModalReducedMotion:
    @pytest.fixture
    def browser_context_args(self, browser_context_args):
        return {**browser_context_args, "reduced_motion": "reduce"}

    def test_closes_immediately_and_page_stays_clickable(self, live_server, page, seed):
        _open_and_dismiss(page, live_server)

        expect(page.locator(OVERLAY)).to_be_hidden()
        assert page.locator(OVERLAY).get_attribute("hidden") is not None

        # The overlay no longer absorbs clicks on the page behind it.
        page.click('.site-nav a[href="/events/"]')
        expect(page).to_have_url(re.compile(r"/events/$"))


class TestConfirmModalDefaultMotion:
    def test_closes_after_transition_without_reduced_motion(self, live_server, page, seed):
        """Regression guard for the pre-existing transitionend path."""
        _open_and_dismiss(page, live_server)

        expect(page.locator(OVERLAY)).to_be_hidden()
        assert page.locator(OVERLAY).get_attribute("hidden") is not None
