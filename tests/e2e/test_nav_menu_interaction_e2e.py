"""E2E: mobile hamburger nav-menu interaction — shared-shell plan
(.docs/plans/2026-07-20-shared-shell-plan.md §D-3).

Mirrors test_account_menu_interaction_e2e.py's open -> Escape -> focus
returns to the trigger contract, but the outside-click behavior is the
opposite by design: the plan (§B, mediated by BIR) calls out that the nav
panel is in-flow (not an overlay like the account menu) and explicitly does
NOT close on outside click — this test pins that as an intentional
assertion, not an oversight.
"""
import pytest

pytestmark = pytest.mark.e2e


def test_320px에서_햄버거_토글을_클릭하면_패널이_열리고_Escape를_누르면_닫히며_포커스가_토글로_돌아오고_패널_밖_클릭으로는_닫히지_않는다(
    live_server, page, seed
):
    page.set_viewport_size({"width": 320, "height": 740})
    page.goto(live_server.url + "/")

    toggle = page.locator("[data-nav-menu-toggle]")
    nav = page.locator("#primary-nav")

    assert toggle.get_attribute("aria-expanded") == "false"
    assert nav.get_attribute("data-expanded") == "false"

    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert nav.get_attribute("data-expanded") == "true"

    links = page.evaluate(
        "() => Array.from(document.querySelectorAll('.site-nav a'))"
        ".map(a => a.getBoundingClientRect().height > 0 && a.getBoundingClientRect().width > 0)"
    )
    assert len(links) == 4
    assert all(links)

    page.keyboard.press("Escape")
    assert toggle.get_attribute("aria-expanded") == "false"
    assert nav.get_attribute("data-expanded") == "false"
    assert page.evaluate(
        "document.activeElement === document.querySelector('[data-nav-menu-toggle]')"
    )

    toggle.click()
    assert nav.get_attribute("data-expanded") == "true"

    page.locator(".site-footer").click()
    assert nav.get_attribute("data-expanded") == "true"


def test_320px에서_햄버거가_열린_채로_계정_메뉴를_열고_Escape를_누르면_계정_메뉴만_닫히고_햄버거는_열린_채로_유지된다(
    live_server, page, seed, login
):
    login(page, live_server.url, "e2e_user@example.com", seed.password)
    page.set_viewport_size({"width": 320, "height": 740})
    page.goto(live_server.url + "/")

    nav_toggle = page.locator("[data-nav-menu-toggle]")
    nav = page.locator("#primary-nav")
    account_toggle = page.locator("[data-account-menu-toggle]")
    account_panel = page.locator("[data-account-menu-panel]")

    nav_toggle.click()
    assert nav_toggle.get_attribute("aria-expanded") == "true"
    assert nav.get_attribute("data-expanded") == "true"

    account_toggle.click()
    assert account_panel.is_visible()

    page.keyboard.press("Escape")

    assert account_panel.is_hidden()
    assert page.evaluate(
        "document.activeElement === document.querySelector('[data-account-menu-toggle]')"
    )

    assert nav_toggle.get_attribute("aria-expanded") == "true"
    assert nav.get_attribute("data-expanded") == "true"
