"""E2E: /staff/drafts/ status filter + pagination across real navigations.

Drives real Chromium: clicking a status chip filters the list and updates
the URL, filter + pager combine (status is preserved across page links), and
an empty-filter result shows the "all"-view escape hatch. The view/pager
logic itself is covered by tests/test_staff_draft_views.py — these confirm
the rendered chips/pager actually work end to end in a browser.
"""
import re

import pytest
from playwright.sync_api import expect

from drafts.models import EventDraft

pytestmark = pytest.mark.e2e

CHIPS = ".chips .chip"


def _seed_drafts(count, status, start=0):
    for i in range(start, start + count):
        EventDraft.objects.create(
            source_url=f"https://example.com/{status}-{i}",
            review_status=status,
        )


class TestStaffDraftsFilter:
    def test_status_chips_render_with_all_active(self, live_server, page, seed, login):
        _seed_drafts(1, EventDraft.ReviewStatus.PENDING)
        _seed_drafts(1, EventDraft.ReviewStatus.APPROVED)
        _seed_drafts(1, EventDraft.ReviewStatus.REJECTED)

        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/drafts/")

        expect(page.locator(CHIPS)).to_have_count(4)
        all_chip = page.locator(CHIPS).first
        expect(all_chip).to_have_class(re.compile(r"\bactive\b"))
        expect(all_chip).to_have_attribute("aria-current", "true")

    def test_clicking_pending_chip_filters_and_marks_active(
        self, live_server, page, seed, login
    ):
        pending = EventDraft.objects.create(
            source_url="https://example.com/pending-1",
            extracted_title="검토 대기 드래프트",
            review_status=EventDraft.ReviewStatus.PENDING,
        )
        EventDraft.objects.create(
            source_url="https://example.com/approved-1",
            extracted_title="승인된 드래프트",
            review_status=EventDraft.ReviewStatus.APPROVED,
        )

        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/drafts/")

        page.click('a.chip[aria-label="검토 대기 필터"]')

        expect(page).to_have_url(f"{live_server.url}/staff/drafts/?status=pending")
        expect(page.locator(".draft-card")).to_have_count(1)
        expect(page.locator(".draft-card").first).to_contain_text("검토 대기 드래프트")
        expect(page.locator('a.chip[aria-label="검토 대기 필터"]')).to_have_class(
            re.compile(r"\bactive\b")
        )

    def test_pager_preserves_status_filter_across_pages(
        self, live_server, page, seed, login
    ):
        _seed_drafts(11, EventDraft.ReviewStatus.PENDING)

        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/drafts/?status=pending")

        expect(page.locator(".draft-card")).to_have_count(10)

        page.click(".pager a:has-text('다음')")

        expect(page).to_have_url(
            f"{live_server.url}/staff/drafts/?page=2&status=pending"
        )
        expect(page.locator(".draft-card")).to_have_count(1)
        expect(page.locator('a.chip[aria-label="검토 대기 필터"]')).to_have_class(
            re.compile(r"\bactive\b")
        )

    def test_empty_status_filter_shows_notice_and_returns_to_all(
        self, live_server, page, seed, login
    ):
        EventDraft.objects.create(
            source_url="https://example.com/pending-only",
            review_status=EventDraft.ReviewStatus.PENDING,
        )

        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/drafts/?status=rejected")

        expect(page.locator(".draft-list")).to_have_count(0)
        notice = page.locator(".panel .notice", has_text="해당 상태의 드래프트가 없습니다")
        expect(notice).to_be_visible()

        notice.locator("a").click()

        expect(page).to_have_url(f"{live_server.url}/staff/drafts/")
        expect(page.locator(".draft-card")).to_have_count(1)
