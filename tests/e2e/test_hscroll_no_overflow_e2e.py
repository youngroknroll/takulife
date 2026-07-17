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

from archive.models import UserEventStatus
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
    def test_스크롤이_필요없는_hscroll_트랙은_마스크를_제거하고_탭_정지점에서_제외된다(self, live_server, page):
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


class TestHomeSnapshotHscrollNonOverflowingState:
    """Same !overflowing path (mask removal + tabindex="-1"), exercised on
    the home collection-snapshot panel's (H-2) 기록 대기 sublist with a
    single card — the newest hscroll render site most likely to hit this
    branch routinely (a fresh user has few unrecorded visits, not many)."""

    def test_홈_스냅샷_기록_대기_트랙이_카드_한_장뿐이면_마스크를_제거하고_탭_정지점에서_제외된다(
        self, live_server, page, seed, login
    ):
        event = Event.objects.create(
            title="기록 대기 단일 카드", publish_status=Event.PublishStatus.PUBLISHED
        )
        UserEventStatus.objects.create(
            user=seed.user, event=event, status=UserEventStatus.Status.VISITED
        )
        page.set_viewport_size({"width": 1280, "height": 1000})

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(live_server.url + "/")

        result = page.evaluate(
            """() => {
                var track = document.getElementById('hscroll-snap-record');
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
