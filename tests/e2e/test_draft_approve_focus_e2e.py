"""E2E regression: draft.js's approval success flow drops keyboard focus.

The approve button held focus at click time; on success draft.js set
`btn.disabled = true` (so an already-approved draft can't be resubmitted)
without moving focus first. A disabled element that holds focus silently
drops it to <body> — a keyboard user loses their place with no
announcement. Verified with real key events only (Enter to activate,
then Tab) — a programmatic `.focus()` call in a test would report success
even with tabindex=-1 set on an element that isn't actually reachable by
Tab, which is not what this regression is about (see
test_status_sibling_focus_e2e.py for the same real-key-event convention).
"""
import pytest

from drafts.models import EventDraft

pytestmark = pytest.mark.e2e


class TestDraftApproveSuccessFocus:
    def test_focus_moves_to_success_region_then_tabs_into_its_link(
        self, live_server, page, seed, login, browser_name
    ):
        if browser_name == "webkit":
            pytest.skip(
                "WebKit skips links in Tab order (macOS convention) — "
                "Tab-to-link assertion is Chromium-scoped"
            )

        draft = EventDraft.objects.create(
            source_url="https://example.com/approve-focus-1",
            extracted_title="포커스 회귀 테스트",
            review_status=EventDraft.ReviewStatus.PENDING,
        )

        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/drafts/{draft.id}/")

        page.locator("#draft-approve-btn").focus()
        page.keyboard.press("Enter")
        # draft.js now confirms through the styled TakuConfirm modal
        # (confirm-modal.js, loaded globally in base.html) instead of a
        # native window.confirm — no page.on("dialog") handler fires for
        # it. Accept via its own 예 button; this intermediate step is
        # outside what this test is about (see module docstring), so a
        # plain click is fine here even though the rest of the test uses
        # real key events on purpose.
        page.click(".confirm-yes")
        page.wait_for_selector("#draft-approve-success:not([hidden])")

        active = page.evaluate("() => document.activeElement.id")
        assert active == "draft-approve-success"

        # tabindex=-1 keeps the <p> itself out of the Tab sequence, but its
        # own child link ("행사 #<id> 보기") is still a normal tab stop —
        # confirms Tab continues forward instead of leaving the document.
        page.keyboard.press("Tab")
        next_active = page.evaluate(
            "() => ({id: document.activeElement.id, tag: document.activeElement.tagName})"
        )
        assert next_active["tag"] == "A"
        assert next_active["id"] != "draft-approve-success"
