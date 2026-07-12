"""E2E: header account-menu disclosure interaction (track-c-spec.md §1
'참고' — a measurable gate: open -> Escape -> focus returns to the trigger).

Ported from event_list.js's region-select dropdown (static/js/shared/
account_menu.js) — same click-toggle/outside-click/Escape contract, but
region-select itself has no e2e pin for it; this one test is pinned because
the design spec explicitly calls it out as the one interaction worth
automating, everything else in the account menu is manual/visual.
"""
import pytest

pytestmark = pytest.mark.e2e


def test_toggle_opens_panel_and_escape_closes_and_returns_focus(
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
