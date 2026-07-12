"""E2E regression: draft.js's edit-form save button after a failed save.

bindEditForm's PATCH callback restored `submitBtn.disabled = false` directly
instead of routing through window.TakuAPI.setLoading (the same helper create/
approve/reject already use). That left the `.is-loading` class stuck on the
button after a failed save — and `.is-loading` sets `pointer-events: none`
(static/css/objects/interaction.css), so a mouse re-click on the save button
was silently swallowed. Only a keyboard Enter (which doesn't go through
pointer hit-testing) could retry.
"""
import json
import re

import pytest
from playwright.sync_api import expect

from drafts.models import EventDraft

pytestmark = pytest.mark.e2e

SAVE_BTN = '#draft-edit-form button[type="submit"]'


class TestDraftEditRetryAfterFailure:
    def test_save_button_recovers_from_failed_save_and_allows_mouse_retry(
        self, live_server, page, seed, login
    ):
        draft = EventDraft.objects.create(
            source_url="https://example.com/edit-retry-1",
            extracted_title="원본 제목",
            review_status=EventDraft.ReviewStatus.PENDING,
        )

        patch_requests = []

        def handle_patch(route, request):
            patch_requests.append(request)
            route.fulfill(
                status=400,
                content_type="application/json",
                body=json.dumps({"detail": "저장에 실패했습니다."}),
            )

        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/drafts/{draft.id}/")
        page.route("**/api/event-drafts/**", handle_patch)

        page.fill("#edit-title", "수정된 제목")
        save_btn = page.locator(SAVE_BTN)
        save_btn.click()

        expect(page.locator("#draft-edit-error")).to_be_visible()
        assert len(patch_requests) == 1

        # Loading state must fully clear after the failure — not just
        # `disabled`, but the .is-loading class too.
        expect(save_btn).to_be_enabled()
        expect(save_btn).not_to_have_class(re.compile(r"\bis-loading\b"))

        # A real mouse click must reach the button (pointer-events must not
        # still be blocked by a lingering .is-loading class).
        save_btn.click()

        assert len(patch_requests) == 2
