"""Tests for the staff-only draft HTML views (event_drafts / event_draft_detail).

Existing tests only exercised the staff *guard* (redirect / not-found). These
cover the populated paths: the list row loop and the detail label rendering.
"""
import pytest

from drafts.models import EventDraft


@pytest.mark.django_db
class TestEventDraftsListView:
    def test_list_renders_draft_rows(self, staff_client, make_draft):
        make_draft("https://example.com/a", extracted_title="드래프트 A", extracted_category="popup_store")
        make_draft("https://example.com/b", extracted_title="드래프트 B")

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "드래프트 A" in body
        assert "드래프트 B" in body


def _seed_drafts(make_draft, count, status=EventDraft.ReviewStatus.PENDING, start=0):
    for i in range(start, start + count):
        make_draft(f"https://example.com/{status}-{i}", review_status=status)


@pytest.mark.django_db
class TestEventDraftsListFilterPagination:
    """/staff/drafts/ status filter + pagination (shared pager, list_drafts)."""

    def test_first_page_caps_at_twenty_with_pager(self, staff_client, make_draft):
        _seed_drafts(make_draft, 21)

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 21
        assert len(page_obj.object_list) == 20
        assert page_obj.has_other_pages() is True

    def test_no_pager_when_within_one_page(self, staff_client, make_draft):
        _seed_drafts(make_draft, 20)

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.context["page_obj"].has_other_pages() is False

    def test_second_page_holds_remainder_and_differs_from_first(self, staff_client, make_draft):
        _seed_drafts(make_draft, 21)

        _, client = staff_client()
        first = client.get("/staff/drafts/")
        second = client.get("/staff/drafts/?page=2")

        assert second.status_code == 200
        second_page = second.context["page_obj"]
        assert second_page.number == 2
        assert len(second_page.object_list) == 1
        first_ids = [row["draft"].id for row in first.context["draft_rows"]]
        second_ids = [row["draft"].id for row in second.context["draft_rows"]]
        assert set(first_ids).isdisjoint(second_ids)

    @pytest.mark.parametrize("page_value", ["abc", "9999", "0"])
    def test_invalid_page_values_return_200(self, staff_client, page_value, make_draft):
        _seed_drafts(make_draft, 21)

        _, client = staff_client()
        resp = client.get(f"/staff/drafts/?page={page_value}")

        assert resp.status_code == 200

    def test_status_filter_shows_only_matching_rows(self, staff_client, make_draft):
        pending = make_draft("https://example.com/pending-1", review_status=EventDraft.ReviewStatus.PENDING)
        make_draft("https://example.com/approved-1", review_status=EventDraft.ReviewStatus.APPROVED)
        make_draft("https://example.com/rejected-1", review_status=EventDraft.ReviewStatus.REJECTED)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending")

        assert resp.status_code == 200
        rows = resp.context["draft_rows"]
        assert [row["draft"].id for row in rows] == [pending.id]

    def test_no_status_returns_all_ordered_by_id_desc(self, staff_client, make_draft):
        first = make_draft("https://example.com/x-1")
        second = make_draft("https://example.com/x-2")

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        rows = resp.context["draft_rows"]
        assert [row["draft"].id for row in rows] == [second.id, first.id]

    def test_unknown_status_falls_back_to_all(self, staff_client, make_draft):
        make_draft("https://example.com/y-1")

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=garbage")

        assert resp.status_code == 200
        assert resp.context["selected_status"] == ""

    def test_pager_query_preserves_status_filter(self, staff_client, make_draft):
        _seed_drafts(make_draft, 21, status=EventDraft.ReviewStatus.PENDING)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending")

        assert resp.status_code == 200
        assert resp.context["pager_query"] == "&status=pending"
        assert b"?page=2&amp;status=pending" in resp.content

    def test_stats_report_totals_not_filtered_subset(self, staff_client, make_draft):
        _seed_drafts(make_draft, 2, status=EventDraft.ReviewStatus.PENDING)
        _seed_drafts(make_draft, 3, status=EventDraft.ReviewStatus.APPROVED)
        _seed_drafts(make_draft, 1, status=EventDraft.ReviewStatus.REJECTED)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending")

        assert resp.status_code == 200
        stats = resp.context["stats"]
        assert stats["pending"] == 2
        assert stats["approved"] == 3
        assert stats["rejected"] == 1

    def test_filtered_status_keeps_order_across_page_boundary(self, staff_client, make_draft):
        _seed_drafts(make_draft, 21, status=EventDraft.ReviewStatus.PENDING)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending&page=2")

        assert resp.status_code == 200
        rows = resp.context["draft_rows"]
        ids = [row["draft"].id for row in rows]
        assert ids == sorted(ids, reverse=True)

    def test_empty_state_when_no_drafts_at_all(self, staff_client):
        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.status_code == 200
        assert "등록된 드래프트가 없습니다" in resp.content.decode()

    def test_empty_state_for_selected_status_with_other_status_present(self, staff_client, make_draft):
        make_draft("https://example.com/only-pending", review_status=EventDraft.ReviewStatus.PENDING)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=rejected")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "해당 상태의 드래프트가 없습니다" in body
        assert "전체 보기" in body
        assert "등록된 드래프트가 없습니다" not in body

    def test_empty_state_falls_back_to_a_when_db_totally_empty_with_status(self, staff_client):
        """Pin: ?status=pending with zero drafts anywhere shows empty-state A
        (creation prompt), not the "no matching status" empty-state B."""
        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending")

        assert resp.status_code == 200
        assert "등록된 드래프트가 없습니다" in resp.content.decode()


@pytest.mark.django_db
class TestEventDraftDetailView:
    def test_existing_draft_renders_with_labels(self, staff_client, make_draft):
        draft = make_draft("https://example.com/c", extracted_title="상세 드래프트", extracted_category="popup_store", extracted_region="seoul")

        _, client = staff_client()
        resp = client.get(f"/staff/drafts/{draft.id}/")

        assert resp.status_code == 200
        assert resp.context["draft"] == draft
        assert resp.context["is_pending"] is True
        # Slugs resolved to human labels.
        assert resp.context["category_label"] == "팝업스토어"
        assert resp.context["region_label"] == "서울"

    def test_missing_draft_shows_not_found_notice(self, staff_client):
        _, client = staff_client()
        resp = client.get("/staff/drafts/999999/")

        assert resp.status_code == 200
        assert resp.context["draft_not_found"] is True
