"""E2E regression: TakuConfirm leaves the background page scrollable while
open (measured: 300px of scroll while the modal sat on top). confirm-modal.js
is loaded globally from base.html, so any public page with enough content to
scroll exercises it — the home page's carousel/sections are used here.
"""
import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

OVERLAY = ".confirm-overlay"


class TestConfirmModalScrollLock:
    def test_확인_모달이_열려있는_동안_배경_스크롤이_잠기고_닫으면_복원된다(
        self, live_server, page, seed
    ):
        page.goto(live_server.url + "/")

        # Not awaited on purpose: TakuConfirm's promise only resolves once
        # 아니오 is clicked below, and blocking here would deadlock the test.
        page.evaluate("() => { window.TakuConfirm('테스트'); }")
        expect(page.locator(OVERLAY)).to_have_class(re.compile(r"is-open"))

        assert page.evaluate("() => window.scrollY") == 0
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(100)
        assert page.evaluate("() => window.scrollY") == 0

        page.click(".confirm-no")
        expect(page.locator(OVERLAY)).to_be_hidden()

        page.mouse.wheel(0, 400)
        page.wait_for_timeout(100)
        assert page.evaluate("() => window.scrollY") > 0
