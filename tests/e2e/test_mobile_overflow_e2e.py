"""E2E: mobile viewport horizontal-overflow smoke (375x812 phone width).

Automated re-run of the manual §10 Gate B check ("320px 이상에서 페이지 단위
수평 스크롤 없음") across the four pages the mobile-first plan flagged —
catches a CSS/JS regression that widens `body.scrollWidth` without waiting
for the next manual pass.
"""
import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 375, "height": 812}}


def _no_horizontal_overflow(page):
    return page.evaluate("document.body.scrollWidth <= window.innerWidth")


class TestMobileOverflowSmoke:
    def test_home_has_no_horizontal_overflow(self, live_server, page, seed):
        page.goto(live_server.url + "/")

        # The hero carousel applies its "fan" layout (transforms) after init —
        # measuring before that would miss the layout the fan settles into.
        page.wait_for_selector("[data-carousel-track].fan")

        assert _no_horizontal_overflow(page)

    def test_event_list_has_no_horizontal_overflow(self, live_server, page, seed):
        page.goto(f"{live_server.url}/events/")

        assert _no_horizontal_overflow(page)

    def test_event_detail_has_no_horizontal_overflow(self, live_server, page, seed):
        event = seed.events[0]
        page.goto(f"{live_server.url}/events/{event.id}/")

        assert _no_horizontal_overflow(page)

    def test_archive_has_no_horizontal_overflow(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/")

        assert _no_horizontal_overflow(page)

    def test_staff_dashboard_has_no_horizontal_overflow(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/dashboard/")

        assert _no_horizontal_overflow(page)
