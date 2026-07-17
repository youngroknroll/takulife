"""E2E regression: carousel.js's auto-shuffle and pointer tracking under a
runtime reduced-motion switch.

createFan() only checked prefers-reduced-motion once, at page-load init
(startAuto() bails when it's set, so the shuffle interval never even starts,
and the pointer handlers were only bound inside `if (!prefersReducedMotion())`)
— but it never re-checked afterward, and loading under reduce skipped binding
the pointer handlers at all. If a visitor loads the page with normal motion
and then flips OS-level "reduce motion" on mid-session, the fan kept
auto-shuffling AND mousemove kept lifting cards; conversely a visitor who
loads under reduce and then switches it off gets no hover tracking at all
until a full reload (docstring's "Reduced-motion: renders a static fan (no
cursor tracking)" contract broken in both directions). matchMedia's change
event had no listener wired to the auto-shuffle, unlike hscroll.js's
autoplay (hscroll.js:195), which does; the pointer handlers themselves used
an init-time gate instead of hscroll.js's shouldAutoplay()-style call-time
recheck. carousel.js is loaded globally on the home page
(templates/core/home.html), so any visit to "/" with popular_rows exercises
it.
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


def _move_mouse_over_first_card(page):
    # Bounding-box-derived coordinates (not fixed pixels) so the move always
    # lands on a real card regardless of viewport/layout.
    box = page.locator(".deck-card").first.bounding_box()
    assert box is not None, ".deck-card bounding box unavailable"
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


class TestCarouselRuntimeReducedMotion:
    def test_런타임에_모션_감소를_켜면_캐러셀_셔플과_포인터_추적이_멈춘다(self, live_server, page, seed):
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

        # Also verify pointer tracking itself is call-time gated, not just
        # the auto-shuffle: moving the mouse across the deck while
        # prefers-reduced-motion is active must not lift any card either.
        before_move = samples[-1]
        _move_mouse_over_first_card(page)
        page.wait_for_timeout(200)
        after_move = _card_transforms(page)
        assert after_move == before_move, (
            "mousemove lifted a card while prefers-reduced-motion is active"
        )


class TestCarouselRuntimeMotionRestored:
    """Loading the page under reduced-motion used to skip binding the
    pointer handlers entirely (init-time `if (!prefersReducedMotion())`
    gate) — flipping reduced-motion back off at runtime left hover tracking
    permanently absent, with no way to recover it short of a full reload."""

    @pytest.fixture
    def browser_context_args(self, browser_context_args):
        return {**browser_context_args, "reduced_motion": "reduce"}

    def test_모션_감소_상태로_로드한_뒤_런타임에_끄면_호버_추적이_재로드_없이_작동한다(
        self, live_server, page, seed
    ):
        page.goto(live_server.url + "/")
        page.wait_for_selector("[data-carousel-track].fan")

        before = _card_transforms(page)

        # Flip reduced-motion off at runtime (fires matchMedia's change
        # event in Chromium) — hover tracking must start working without a
        # reload.
        page.emulate_media(reduced_motion="no-preference")
        page.wait_for_timeout(200)

        _move_mouse_over_first_card(page)
        page.wait_for_timeout(200)
        after = _card_transforms(page)

        assert after != before, (
            "hover tracking never started after switching reduced-motion off at runtime"
        )
