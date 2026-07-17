"""E2E: header account-menu disclosure interaction — a measurable gate:
open -> Escape -> focus returns to the trigger.

Ported from event_list.js's region-select dropdown (static/js/shared/
account_menu.js) — same click-toggle/outside-click/Escape contract, but
region-select itself has no e2e pin for it; this one interaction is pinned
because it is the one part of the account menu explicit enough to verify
mechanically (the `hidden` attribute toggling plus document.activeElement),
while everything else about the menu (visual layout, hover/focus colors) is
manual/visual only.
"""
import pytest

pytestmark = pytest.mark.e2e


def test_계정_메뉴_토글을_클릭하면_패널이_열리고_Escape를_누르면_패널이_닫히며_포커스가_토글로_돌아온다(
    live_server, page, seed, login
):
    login(page, live_server.url, "e2e_user@example.com", seed.password)
    page.goto(live_server.url + "/")

    toggle = page.locator("[data-account-menu-toggle]")
    panel = page.locator("[data-account-menu-panel]")

    assert panel.is_hidden()

    toggle.click()
    assert panel.is_visible()

    page.keyboard.press("Escape")
    assert panel.is_hidden()
    assert page.evaluate(
        "document.activeElement === document.querySelector('[data-account-menu-toggle]')"
    )
