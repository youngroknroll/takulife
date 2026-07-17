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

    def test_reduced_motion에서_모달을_닫으면_즉시_사라지고_배경이_클릭_가능해진다(self, live_server, page, seed):
        _open_and_dismiss(page, live_server)

        expect(page.locator(OVERLAY)).to_be_hidden()
        assert page.locator(OVERLAY).get_attribute("hidden") is not None

        # The overlay no longer absorbs clicks on the page behind it.
        page.click('.site-nav a[href="/events/"]')
        expect(page).to_have_url(re.compile(r"/events/$"))


class TestConfirmModalDefaultMotion:
    def test_reduced_motion이_아니면_트랜지션_종료_후_모달이_닫힌다(self, live_server, page, seed):
        """Regression guard for the pre-existing transitionend path."""
        _open_and_dismiss(page, live_server)

        expect(page.locator(OVERLAY)).to_be_hidden()
        assert page.locator(OVERLAY).get_attribute("hidden") is not None


class TestConfirmModalTransitionDisabledByStylesheet:
    """The matchMedia(reduced-motion) check only covers one of several ways a
    transition can fail to run — a page stylesheet stripping `transition`
    (e.g. a print sheet, some global motion toggle unrelated to the OS
    setting) leaves close()'s old transitionend-only wait with nothing to
    ever fire, so [hidden] never gets restored and the overlay stays up,
    silently absorbing clicks on the page behind it."""

    def test_스타일시트가_트랜지션을_제거해도_모달이_닫히고_배경이_클릭_가능해진다(self, live_server, page, seed):
        page.goto(live_server.url + "/")
        page.add_style_tag(content=".confirm-overlay,.confirm-dialog{transition:none !important;}")

        # Not awaited on purpose: TakuConfirm's promise only resolves once
        # 아니오 is clicked below, and blocking here would deadlock the test.
        page.evaluate("() => { window.TakuConfirm('테스트'); }")
        expect(page.locator(OVERLAY)).to_have_class(re.compile(r"is-open"))
        page.click(".confirm-no")

        expect(page.locator(OVERLAY)).to_be_hidden()
        assert page.locator(OVERLAY).get_attribute("hidden") is not None

        # The overlay no longer absorbs clicks on the page behind it.
        page.click('.site-nav a[href="/events/"]')
        expect(page).to_have_url(re.compile(r"/events/$"))


class TestConfirmModalReopenDuringClose:
    """Reopening before the previous close() transition finishes must not
    leave a stale transitionend listener / setTimeout armed against the
    overlay's *next* open — otherwise the previous close's cleanup fires
    mid-open and hides a modal that is supposed to be open."""

    def test_닫힘_트랜지션_중에_다시_열면_모달이_열린_상태로_유지된다(self, live_server, page, seed):
        page.goto(live_server.url + "/")

        page.evaluate("() => { window.TakuConfirm('첫번째'); }")
        expect(page.locator(OVERLAY)).to_have_class(re.compile(r"is-open"))
        page.click(".confirm-no")

        # A short delay lets the close transition actually start (removing
        # is-open and re-adding it again within the same style flush would
        # coalesce into a no-op transition that never fires transitionend at
        # all, masking the bug) — but still well inside the .15s CSS
        # transition, so the reopen genuinely interrupts it mid-flight.
        page.wait_for_timeout(60)

        page.evaluate("() => { window.TakuConfirm('둘째'); }")

        # Outlast the original close transition/backstop before asserting —
        # if a stale listener/timer survived the reopen, it would fire and
        # hide the (now open) overlay somewhere in this window.
        page.wait_for_timeout(500)

        expect(page.locator(OVERLAY)).to_have_class(re.compile(r"is-open"))
        assert page.locator(OVERLAY).get_attribute("hidden") is None
