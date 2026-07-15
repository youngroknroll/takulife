"""Tests for pagination and search on /archive/items/ (비공식 personal entries).

Behavior under test:
- 7 entries are paginated at 5 per page; page_obj is in the context.
- Summary card counts (total/place/goods) reflect ALL entries, never the filtered subset.
- ?q=<term> filters the displayed entry_rows server-side.
- has_entries reflects whether the user owns any personal entries at all;
  a zero-hit search with q still shows has_entries=True when entries exist.
- has_query in context distinguishes "user typed something" from "no search".
- pager_query carries ?q=... so page links preserve the active search.
"""
import pytest

from archive.models import PersonalEntry


# ---------------------------------------------------------------------------
# Basic pagination
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsPagination:
    """7 items paginate at 5/page; page_obj is in the template context."""

    def test_first_page_holds_five(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7)

        resp = client.get("/archive/items/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert page_obj.paginator.num_pages == 2
        assert len(page_obj.object_list) == 5

    def test_second_page_holds_two(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7)

        resp = client.get("/archive/items/?page=2")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.number == 2
        assert len(page_obj.object_list) == 2

    def test_single_page_when_five_or_fewer(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 4)

        resp = client.get("/archive/items/")

        assert resp.context["page_obj"].paginator.num_pages == 1


# ---------------------------------------------------------------------------
# Summary counts from ALL entries (not filtered/paginated subset)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsSummaryCounts:
    """Summary card counts are always unfiltered totals."""

    def test_counts_total(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7, kind=PersonalEntry.Kind.PLACE)

        resp = client.get("/archive/items/")

        assert resp.context["total_count"] == 7
        assert "place_count" not in resp.context
        assert "goods_count" not in resp.context

    def test_summary_unchanged_by_q_filter(self, user_client, make_entries):
        """total_count does not shrink when q narrows entry_rows."""
        user, client = user_client()
        make_entries(user, 7, kind=PersonalEntry.Kind.PLACE, title_prefix="항목")

        # q="00" would match only "항목 00"
        resp = client.get("/archive/items/?q=00")

        # Summary must still report 7, not the filtered count
        assert resp.context["total_count"] == 7

    def test_has_entries_true_even_when_q_yields_zero(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="내 항목")

        resp = client.get("/archive/items/?q=없는검색어XYZ")

        assert resp.status_code == 200
        assert resp.context["has_entries"] is True  # 1 entry exists regardless


# ---------------------------------------------------------------------------
# q search on /archive/items/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsSearch:
    """?q= filters entry_rows on /archive/items/."""

    def test_q_filters_displayed_entry_rows(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="매칭 항목")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="다른 항목")

        resp = client.get("/archive/items/?q=매칭")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "매칭 항목" in titles
        assert "다른 항목" not in titles

    def test_q_filters_paginator_count(self, user_client, make_entry):
        """page_obj.paginator.count reflects the filtered (q-narrowed) count."""
        user, client = user_client()
        for i in range(3):
            make_entry(user, kind=PersonalEntry.Kind.PLACE, title=f"매칭{i}")
        for i in range(4):
            make_entry(user, kind=PersonalEntry.Kind.PLACE, title=f"기타{i}")

        resp = client.get("/archive/items/?q=매칭")

        assert resp.context["page_obj"].paginator.count == 3

    def test_empty_q_shows_all_entries(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 3)

        resp = client.get("/archive/items/?q=")

        assert resp.context["page_obj"].paginator.count == 3
        assert resp.context["has_query"] is False


# ---------------------------------------------------------------------------
# Context keys: q, has_query, pager_query
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsContextKeys:
    """page_obj, q, has_query, pager_query must all be present in the context."""

    def test_q_and_has_query_in_context(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/items/?q=검색어")

        assert resp.context["q"] == "검색어"
        assert resp.context["has_query"] is True

    def test_no_q_param_gives_empty_q_and_false_has_query(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/items/")

        assert resp.context["q"] == ""
        assert resp.context["has_query"] is False

    def test_pager_query_carries_q(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7)  # 2 pages

        resp = client.get("/archive/items/?q=항목")

        pager_query = resp.context["pager_query"]
        assert "q=" in pager_query

    def test_pager_query_empty_without_q(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7)

        resp = client.get("/archive/items/")

        assert resp.context["pager_query"] == ""

    def test_whitespace_q_normalised_to_empty(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 3)

        resp = client.get("/archive/items/?q=   ")

        assert resp.context["q"] == ""
        assert resp.context["has_query"] is False
        assert resp.context["page_obj"].paginator.count == 3

    def test_long_q_truncated_no_server_error(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/items/?q=" + "Z" * 200)

        assert resp.status_code == 200
        assert len(resp.context["q"]) <= 100
