"""Tests for pagination on the three archive SSR list pages.

Behavior under test:
- 기록장 (/archive/) paginates 저장한 행사 at 10 per page.
- 예정 목록 (/archive/statuses/) paginates the same status list at 5 per page,
  preserving the ?status= filter across page links.
- 방문 기록 (/archive/visits/) paginates the timeline at 5 per page while the
  summary cards (누적 방문 / 메모 있음) keep reporting totals across all records.
"""
import pytest

from archive.models import UserEventStatus, VisitRecord


def _make_statuses(user, make_event, count, status=UserEventStatus.Status.PLANNED):
    # One status per distinct event (user+event is unique). Events carry no
    # dates, so the derived status stays exactly `status` (no auto-miss overlay).
    for i in range(count):
        event = make_event(title=f"Event {i:02d}")
        UserEventStatus.objects.create(user=user, event=event, status=status)


@pytest.mark.django_db
class TestArchiveRecordPagination:
    """기록장 (/archive/) — 저장한 행사, 10 per page."""

    def test_first_page_caps_at_ten(self, user_client, make_event):
        user, client = user_client()
        _make_statuses(user, make_event, 12)

        resp = client.get("/archive/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 12
        assert page_obj.paginator.num_pages == 2
        assert page_obj.number == 1
        assert len(page_obj.object_list) == 10
        assert len(resp.context["status_rows"]) == 10
        assert resp.context["has_statuses"] is True

    def test_second_page_holds_remainder(self, user_client, make_event):
        user, client = user_client()
        _make_statuses(user, make_event, 12)

        resp = client.get("/archive/?page=2")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.number == 2
        assert len(page_obj.object_list) == 2

    def test_no_pager_when_within_one_page(self, user_client, make_event):
        user, client = user_client()
        _make_statuses(user, make_event, 8)

        resp = client.get("/archive/")

        assert resp.context["page_obj"].paginator.num_pages == 1
        assert resp.context["page_obj"].has_other_pages() is False


@pytest.mark.django_db
class TestArchiveStatusesPagination:
    """예정 목록 (/archive/statuses/) — 5 per page, filter-preserving."""

    def test_first_page_caps_at_five(self, user_client, make_event):
        user, client = user_client()
        _make_statuses(user, make_event, 7)

        resp = client.get("/archive/statuses/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert page_obj.paginator.num_pages == 2
        assert len(page_obj.object_list) == 5

    def test_second_page_holds_remainder(self, user_client, make_event):
        user, client = user_client()
        _make_statuses(user, make_event, 7)

        resp = client.get("/archive/statuses/?page=2")

        assert resp.context["page_obj"].number == 2
        assert len(resp.context["page_obj"].object_list) == 2

    def test_status_filter_preserved_in_pager_links(self, user_client, make_event):
        user, client = user_client()
        _make_statuses(user, make_event, 7, status=UserEventStatus.Status.PLANNED)

        resp = client.get("/archive/statuses/?status=planned")

        assert resp.status_code == 200
        # The filter tail is exposed for the pager and the windowed page links
        # carry it so paging never drops the active filter.
        assert resp.context["pager_query"] == "&status=planned"
        assert resp.context["page_obj"].paginator.count == 7
        # The & in the querystring tail is auto-escaped in the href attribute
        # (correct HTML; the browser decodes it back to & when navigating).
        assert b"?page=2&amp;status=planned" in resp.content

    def test_filtered_second_page_keeps_only_matching_rows(self, user_client, make_event):
        user, client = user_client()
        _make_statuses(user, make_event, 7, status=UserEventStatus.Status.PLANNED)
        # Visited rows must not leak into the planned-filtered list/count.
        _make_statuses(user, make_event, 3, status=UserEventStatus.Status.VISITED)

        resp = client.get("/archive/statuses/?status=planned&page=2")

        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert len(page_obj.object_list) == 2


@pytest.mark.django_db
class TestArchiveVisitsPagination:
    """방문 기록 (/archive/visits/) — 5 per page; summaries stay totals."""

    def _make_visits(self, user, make_event, count, with_memo=0):
        for i in range(count):
            event = make_event(title=f"Visited {i:02d}")
            VisitRecord.objects.create(
                user=user,
                event=event,
                visited_on=f"2026-05-{(i % 27) + 1:02d}",
                short_review="좋았어요" if i < with_memo else "",
            )

    def test_first_page_caps_at_five(self, user_client, make_event):
        user, client = user_client()
        self._make_visits(user, make_event, 7)

        resp = client.get("/archive/visits/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert page_obj.paginator.num_pages == 2
        assert len(page_obj.object_list) == 5
        assert len(resp.context["visit_rows"]) == 5

    def test_second_page_holds_remainder(self, user_client, make_event):
        user, client = user_client()
        self._make_visits(user, make_event, 7)

        resp = client.get("/archive/visits/?page=2")

        assert len(resp.context["page_obj"].object_list) == 2

    def test_summary_counts_report_totals_not_page(self, user_client, make_event):
        user, client = user_client()
        self._make_visits(user, make_event, 7, with_memo=3)

        resp = client.get("/archive/visits/")

        # Page shows 5 rows, but the summary cards count across all 7 records.
        assert resp.context["total_count"] == 7
        assert resp.context["memo_count"] == 3
        assert len(resp.context["visit_rows"]) == 5
        assert resp.context["has_visits"] is True
