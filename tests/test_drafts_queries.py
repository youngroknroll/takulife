"""Tests for drafts/queries.py: list_drafts() and DRAFT_LISTING_PAGE_SIZE.

Covers:
- list_drafts() default (no status) returns all drafts ordered by -id
- list_drafts(status=...) filters correctly per review_status
- Filtered results preserve -id ordering
- Unknown status value returns an empty queryset (function-level contract)
- Counts are asserted with N>=2 per status to avoid false-confidence
  regressions (filter vs exists)
- DRAFT_LISTING_PAGE_SIZE constant equals 20
"""
import pytest

from drafts.models import EventDraft


@pytest.mark.django_db
class TestListDrafts:
    def test_no_status_filter_returns_all_drafts_ordered_by_id_desc(self):
        from drafts.queries import list_drafts

        first = EventDraft.objects.create(source_url="https://example.com/1")
        second = EventDraft.objects.create(source_url="https://example.com/2")
        third = EventDraft.objects.create(source_url="https://example.com/3")

        result = list(list_drafts())

        assert result == [third, second, first]

    def test_pending_filter_excludes_approved_and_rejected(self):
        from drafts.queries import list_drafts

        pending = EventDraft.objects.create(source_url="https://example.com/pending")
        EventDraft.objects.create(
            source_url="https://example.com/approved",
            review_status=EventDraft.ReviewStatus.APPROVED,
        )
        EventDraft.objects.create(
            source_url="https://example.com/rejected",
            review_status=EventDraft.ReviewStatus.REJECTED,
        )

        result = list(list_drafts(status=EventDraft.ReviewStatus.PENDING))

        assert result == [pending]

    def test_filter_result_still_ordered_by_id_desc(self):
        from drafts.queries import list_drafts

        older = EventDraft.objects.create(
            source_url="https://example.com/older-pending",
        )
        EventDraft.objects.create(
            source_url="https://example.com/approved-between",
            review_status=EventDraft.ReviewStatus.APPROVED,
        )
        newer = EventDraft.objects.create(
            source_url="https://example.com/newer-pending",
        )

        result = list(list_drafts(status=EventDraft.ReviewStatus.PENDING))

        assert result == [newer, older]

    def test_unknown_status_returns_empty_queryset(self):
        from drafts.queries import list_drafts

        EventDraft.objects.create(source_url="https://example.com/only-pending")

        result = list(list_drafts(status="garbage"))

        assert result == []

    def test_status_filter_counts_are_reliable_with_multiple_records(self):
        from drafts.queries import list_drafts

        for i in range(2):
            EventDraft.objects.create(source_url=f"https://example.com/pending-{i}")
        for i in range(3):
            EventDraft.objects.create(
                source_url=f"https://example.com/approved-{i}",
                review_status=EventDraft.ReviewStatus.APPROVED,
            )
        for i in range(2):
            EventDraft.objects.create(
                source_url=f"https://example.com/rejected-{i}",
                review_status=EventDraft.ReviewStatus.REJECTED,
            )

        assert list_drafts(status=EventDraft.ReviewStatus.PENDING).count() == 2
        assert list_drafts(status=EventDraft.ReviewStatus.APPROVED).count() == 3
        assert list_drafts(status=EventDraft.ReviewStatus.REJECTED).count() == 2


def test_draft_listing_page_size_constant_is_20():
    from drafts.queries import DRAFT_LISTING_PAGE_SIZE

    assert DRAFT_LISTING_PAGE_SIZE == 20
