"""E2E regression: long titles must clamp to a fixed number of lines instead
of stretching the card's vertical rhythm on mobile (375x812 phone width).

Both the event list card title (event_list.css .event-card h2 a) and the
archive status-card title (components/cards.css .status-card h3) render a
free-text title with no length cap — a long title used to grow the card as
tall as the text needed instead of clamping, unlike the home poster card
title (home.css .poster-card-title a), which already clamps to 2 lines.
"""
import pytest

from archive.models import UserEventStatus
from events.models import Event

pytestmark = pytest.mark.e2e

LONG_TITLE = "아주 길고 긴 이벤트 제목이 두 줄을 넘어가지 않고 잘려야 합니다 " * 3


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 375, "height": 812}}


def _clamped_to_two_lines(page, selector):
    return page.evaluate(
        """(selector) => {
            const el = document.querySelector(selector);
            const cs = getComputedStyle(el);
            const lineHeight = parseFloat(cs.lineHeight);
            const maxHeight = lineHeight * 2 + 2; // +2px rounding tolerance
            return el.getBoundingClientRect().height <= maxHeight;
        }""",
        selector,
    )


class TestEventListCardTitleClamp:
    def test_행사_목록_카드에서_긴_제목은_두_줄로_클램프된다(self, live_server, page, seed):
        event = Event.objects.create(
            title=LONG_TITLE,
            publish_status=Event.PublishStatus.PUBLISHED,
            official_url="https://example.com/long-title-event",
        )

        page.goto(f"{live_server.url}/events/")

        assert _clamped_to_two_lines(page, f'.event-card h2 a[href="/events/{event.id}/"]')


class TestArchiveStatusCardTitleClamp:
    def test_나의_일정_카드에서_긴_제목은_두_줄로_클램프되고_상태_버튼은_최소_높이를_유지한다(
        self, live_server, page, seed, login
    ):
        event = Event.objects.create(
            title=LONG_TITLE,
            publish_status=Event.PublishStatus.PUBLISHED,
            official_url="https://example.com/long-title-status",
        )
        UserEventStatus.objects.create(user=seed.user, event=event, status="planned")

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        card = page.locator(".status-card").filter(has_text=LONG_TITLE[:20])
        title = card.locator("h3")
        title_height = title.bounding_box()["height"]
        line_height = page.evaluate(
            "(el) => parseFloat(getComputedStyle(el).lineHeight)",
            title.element_handle(),
        )
        assert title_height <= line_height * 2 + 2

        status_btn_height = card.locator(".status-btn").first.bounding_box()["height"]
        assert status_btn_height >= 32
