"""E2E regression: status.js's sibling-lock focus handling.

handleClick disables every other `.status-btn` in the same
[data-status-error-container] while a request is in flight, so a second
click can't race it (Slow 3G repro history). Disabling the *focused*
sibling makes the browser bounce focus to <body> with no announcement — a
keyboard/screen-reader user loses their place. status.js remembers which
sibling held focus and restores it once the siblings are unlocked again —
but only as a fallback: since the ARIA restoration stage 2 track,
showInlineError() moves focus onto the rendered `.status-inline-error`
message on a failure path, and unlockSiblings()'s restore guard only
restores the remembered sibling when `document.activeElement` is still
`<body>` (i.e. nothing else has claimed focus in the meantime). On a
failure, the inline error wins the focus; the sibling-restore path is a
fallback for cases where nothing else claims focus first.

Uses the event detail page's "참여 상태" status-choices row (three sibling
.status-btn controls: 방문 예정 / 방문 완료 / 놓침). window.TakuAPI.post is
monkey-patched to return a promise the test controls directly (instead of a
real network delay via page.route, whose Python-side blocking would stall
Playwright's own message dispatch and produce unreliable timing) — this
pins the in-flight window deterministically so the mid-flight assertions
never race the request's real resolution.

WebKit-scoped, skipped there: not a product defect — WebKit's blur-on-
disable timing differs from Chromium (disabling the focused sibling doesn't
reliably bounce focus to <body> in the same synchronous window this test
observes it in), which also means the focus-restore behavior itself is
moot when the browser never dropped focus in the first place. Measured
flaky on webkit before the skip was added: 3 isolated reruns, 2 failed / 1
passed (same assertion, same code, no product change between runs).
"""
import pytest
from playwright.sync_api import expect

from events.models import Event

pytestmark = pytest.mark.e2e

PLANNED_BTN = ".status-btn.planned"
VISITED_BTN = ".status-btn.visited"

# Stubs window.TakuAPI.post with a promise that only resolves once the test
# calls window.__resolveStatusRequest(...) — pins the in-flight window open
# for as long as the test needs it, deterministically.
STUB_POST = """
() => {
  window.TakuAPI.post = function () {
    return new Promise(function (resolve) {
      window.__resolveStatusRequest = resolve;
    });
  };
}
"""


class TestStatusSiblingLockFocus:
    def test_실패로_형제_잠금이_해제되면_포커스가_인라인_에러로_이동한다(
        self, live_server, page, seed, login, browser_name
    ):
        if browser_name == "webkit":
            pytest.skip(
                "WebKit's blur-on-disable timing differs from Chromium; "
                "the focus-restore assertions are Chromium-scoped"
            )

        fresh_event = Event.objects.create(
            title="포커스 회귀 테스트 행사", publish_status=Event.PublishStatus.PUBLISHED
        )

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/events/{fresh_event.id}/")
        expect(page.locator(PLANNED_BTN)).to_be_visible()

        page.evaluate(STUB_POST)

        page.evaluate(f"document.querySelector({PLANNED_BTN!r}).focus()")
        assert page.evaluate(
            f"document.activeElement === document.querySelector({PLANNED_BTN!r})"
        )

        # Trigger the other status button programmatically (no page.click —
        # a real click would itself move focus onto the clicked element,
        # muddying which focus change the assertions below are about).
        page.evaluate(f"document.querySelector({VISITED_BTN!r}).click()")

        # Mid-flight (the stubbed request never resolves until we tell it
        # to): the sibling lock disabled 방문 예정, which bounced focus to
        # <body>.
        expect(page.locator(PLANNED_BTN)).to_be_disabled()
        assert page.evaluate("document.activeElement === document.body")

        # Resolve as a network failure (status: 0) — the same shape
        # TakuAPI.post's own catch produces — so the non-reload error branch
        # runs and unlockSiblings() fires in the `finally`.
        page.evaluate("() => window.__resolveStatusRequest({ ok: false, status: 0, data: null })")

        # Once siblings unlock, the sibling lock itself is still lifted (the
        # regression this test protects) — but focus does NOT return to the
        # sibling: showInlineError() has already moved it onto the rendered
        # inline error message, and unlockSiblings()'s restore guard only
        # restores the remembered sibling when activeElement is still
        # <body>, which it no longer is.
        expect(page.locator(PLANNED_BTN)).to_be_enabled()
        assert page.evaluate(
            "document.activeElement === document.querySelector('.status-inline-error')"
        )
