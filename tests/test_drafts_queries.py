"""Tests for drafts/queries.py: list_drafts() and DRAFT_LISTING_PAGE_SIZE.

Covers:
- list_drafts() default (no status) returns all drafts ordered by -id
- list_drafts(status=...) filters correctly per review_status
- Filtered results preserve -id ordering
- Unknown status value returns an empty queryset (function-level contract)
- Counts are asserted with N>=2 per status to avoid false-confidence
  regressions (filter vs exists)
- DRAFT_LISTING_PAGE_SIZE constant equals 20
- list_draft_sources() (PR-5b staff dashboard freshness): ordered by
  -enabled, name — the staff/views.py dashboard() view must call this
  helper rather than querying DraftSource itself (prompt_plan.md §3-1-5).
"""
import pytest

from drafts.models import DraftSource, EventDraft


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


@pytest.mark.django_db
class TestListDraftSources:
    def test_orders_enabled_sources_before_disabled(self):
        from drafts.queries import list_draft_sources

        disabled = DraftSource.objects.create(
            name="disabled-source",
            url="https://example.com/disabled-feed/",
            source_type=DraftSource.SourceType.RSS,
            enabled=False,
        )
        enabled = DraftSource.objects.create(
            name="enabled-source",
            url="https://example.com/enabled-feed/",
            source_type=DraftSource.SourceType.RSS,
            enabled=True,
        )

        result = list(list_draft_sources())

        assert result == [enabled, disabled]

    def test_orders_by_name_within_same_enabled_state(self):
        from drafts.queries import list_draft_sources

        zeta = DraftSource.objects.create(
            name="zeta",
            url="https://example.com/zeta/",
            source_type=DraftSource.SourceType.SITEMAP,
            enabled=True,
        )
        alpha = DraftSource.objects.create(
            name="alpha",
            url="https://example.com/alpha/",
            source_type=DraftSource.SourceType.SITEMAP,
            enabled=True,
        )

        result = list(list_draft_sources())

        assert result == [alpha, zeta]

    def test_returns_empty_when_no_sources_exist(self):
        from drafts.queries import list_draft_sources

        result = list(list_draft_sources())

        assert result == []


@pytest.mark.django_db
class TestEnabledDraftSourcesExist:
    def test_returns_false_when_no_sources_exist(self):
        from drafts.queries import enabled_draft_sources_exist

        assert enabled_draft_sources_exist() is False

    def test_returns_false_when_only_disabled_sources_exist(self):
        from drafts.queries import enabled_draft_sources_exist

        DraftSource.objects.create(
            name="disabled-source",
            url="https://example.com/disabled-feed/",
            source_type=DraftSource.SourceType.RSS,
            enabled=False,
        )

        assert enabled_draft_sources_exist() is False

    def test_returns_true_when_an_enabled_source_exists(self):
        from drafts.queries import enabled_draft_sources_exist

        DraftSource.objects.create(
            name="enabled-source",
            url="https://example.com/enabled-feed/",
            source_type=DraftSource.SourceType.RSS,
            enabled=True,
        )

        assert enabled_draft_sources_exist() is True
