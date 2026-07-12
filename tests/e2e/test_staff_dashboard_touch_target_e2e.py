"""E2E: /staff/dashboard/ .action-button touch target size.

dashboard.html's "지금 수집" button only loaded staff_console.css, which had
no .action-button definition until this track — the button rendered at raw
UA defaults (~22px tall) instead of the project's 44px touch-target
convention (event_list.css .event-card .interest-btn, event_detail.css
§5.4). Mirrors the .status-btn min-height assertion pattern already used in
tests/e2e/test_mobile_card_clamp_e2e.py.
"""
import pytest

pytestmark = pytest.mark.e2e


class TestStaffDashboardActionButtonTouchTarget:
    def test_action_button_meets_min_height(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/dashboard/")

        height = page.locator(".action-button").first.bounding_box()["height"]
        assert height >= 44
