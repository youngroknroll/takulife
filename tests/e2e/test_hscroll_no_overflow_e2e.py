"""E2E regression: hscroll.js's non-overflowing state (update()'s
`!overflowing` branch) left two artifacts behind once fix(home):
e1034a3 made a few-card section (e.g. 곧 종료돼요 with 3 cards) hit this
path routinely instead of rarely.

1. It only removed .at-start/.at-end instead of adding both — the wrap's
   base mask-image is a two-sided edge fade, and only .at-start.at-end
   together (hscroll.css) resolve to mask-image: none. Removing the
   classes left the two-sided fade applied over content that never
   scrolls, visibly clipping the first card's left edge (chrome-devtools
   screenshot confirmed this, 1280px, closing 3 cards).
2. [data-hscroll-track] keeps its template tabindex="0" forever, so a
   non-scrolling track (nothing to Tab *to* by scrolling) stays a Tab stop
   with no purpose.

Reproduces the dev-data shape from the home-slider-unify track (few
closing cards, desktop viewport) so this path is actually exercised.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch

from events.models import Event

pytestmark = pytest.mark.e2e


def _seed_few_closing_rows(today):
    for i in range(3):
        Event.objects.create(
            title=f"Closing {i}",
            publish_status=Event.PublishStatus.PUBLISHED,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=i % 5 + 1),
        )


class TestHscrollNonOverflowingState:
    def test_non_overflowing_track_drops_mask_and_tab_stop(self, live_server, page):
        today = date(2026, 6, 26)
        _seed_few_closing_rows(today)
        page.set_viewport_size({"width": 1280, "height": 1000})

        with patch("core.views.timezone.localdate", return_value=today):
            page.goto(live_server.url + "/")

        result = page.evaluate(
            """() => {
                var track = document.getElementById('hscroll-closing');
                var wrap = track.closest('.hscroll-wrap');
                return {
                    tabIndex: track.getAttribute('tabindex'),
                    maskImage: getComputedStyle(wrap).maskImage
                        || getComputedStyle(wrap).webkitMaskImage,
                    hasAtStart: wrap.classList.contains('at-start'),
                    hasAtEnd: wrap.classList.contains('at-end'),
                };
            }"""
        )

        assert result["tabIndex"] == "-1"
        assert result["maskImage"] == "none"
        assert result["hasAtStart"] is True
        assert result["hasAtEnd"] is True
