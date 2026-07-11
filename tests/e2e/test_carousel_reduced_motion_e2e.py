"""E2E regression: carousel.js's auto-shuffle under a runtime reduced-motion
switch.

createFan() only checked prefers-reduced-motion once, at page-load init
(startAuto() bails when it's set, so the shuffle interval never even starts) —
but it never re-checked afterward. If a visitor loads the page with normal
motion and then flips OS-level "reduce motion" on mid-session, the fan kept
auto-shuffling: matchMedia's change event had no listener wired to it, unlike
hscroll.js's autoplay (hscroll.js:195), which does. carousel.js is loaded
globally on the home page (templates/core/home.html), so any visit to "/"
with popular_rows exercises it.
"""
import pytest

pytestmark = pytest.mark.e2e

# auto-shuffle ticks every AUTO_INTERVAL=1300ms (carousel.js).
TICK_MS = 1300
SAMPLE_INTERVAL_MS = 700
# ~3.5s of polling — comfortably more than two ticks, so a bug that only
# resumes shuffling for a tick or two can't hide between two endpoint checks.
SAMPLE_COUNT = 5


def _card_transforms(page):
    return page.evaluate(
        "Array.from(document.querySelectorAll('.deck-card')).map(el => el.style.transform)"
    )


def _sample_transforms(page, count, interval_ms):
    samples = []
    for _ in range(count):
        samples.append(_card_transforms(page))
        page.wait_for_timeout(interval_ms)
    return samples


class TestCarouselRuntimeReducedMotion:
    def test_shuffle_stops_reacting_to_runtime_reduced_motion_switch(self, live_server, page, seed):
        page.goto(live_server.url + "/")
        page.wait_for_selector("[data-carousel-track].fan")

        initial = _card_transforms(page)

        # Sanity check: with normal motion, the idle shuffle changes the
        # deck's transforms at least once within a couple of ticks — confirms
        # the test's timing assumptions before exercising the runtime switch.
        page.wait_for_function(
            "(initial) => JSON.stringify("
            "Array.from(document.querySelectorAll('.deck-card')).map(el => el.style.transform)"
            ") !== JSON.stringify(initial)",
            arg=initial,
            timeout=TICK_MS * 3,
        )

        # Flip reduced-motion on at runtime (fires matchMedia's change event
        # in Chromium) — the fan must stop shuffling and settle statically.
        page.emulate_media(reduced_motion="reduce")
        page.wait_for_timeout(300)

        # Sample repeatedly over several would-be tick intervals. Comparing
        # only two endpoints would risk a false pass: the deck's bounce
        # pattern can land back on the same transforms after an even number
        # of ticks, masking a shuffle that never actually stopped.
        samples = _sample_transforms(page, SAMPLE_COUNT, SAMPLE_INTERVAL_MS)
        assert all(sample == samples[0] for sample in samples), (
            "deck kept shuffling after prefers-reduced-motion changed at runtime: "
            + str(samples)
        )
