"""Tests for server-side filter/search/pagination on /archive/visits/.

Behavior under test:
- filter=unofficial narrows results to personal-entry visits only.
  Official rows must not leak; summary cards (total_count/memo_count) report
  TOTAL across ALL records, not just the filtered subset.
- filter=cat:<label> OR-matches official records (by category code) and
  unofficial records (by raw category label stored on PersonalEntry).
- Unrecognised filter values (unknown slug, "cat:", "cat:<unknown label>")
  fall back to no filter; response is always 200 (no 500).
- categories and has_unofficial are derived from ALL visit records, not just
  the current page — a filter chip must never disappear due to pagination.
- pager_query simultaneously preserves filter and q across page links.
"""
import pytest

from archive.models import PersonalEntry, VisitRecord


def _make_official_visits(user, make_event, count, *, category="popup_store", with_memo=False, date_prefix="2026-05"):
    for i in range(count):
        ev = make_event(title=f"공식{i:02d}", category=category)
        VisitRecord.objects.create(
            user=user,
            event=ev,
            visited_on=f"{date_prefix}-{i + 1:02d}",
            short_review="좋았어요" if with_memo else "",
        )


def _make_unofficial_visits(user, count, *, category="팝업스토어", with_memo=False, date_prefix="2026-06"):
    for i in range(count):
        entry = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE,
            title=f"비공식{i:02d}", category=category,
        )
        VisitRecord.objects.create(
            user=user,
            personal_entry=entry,
            visited_on=f"{date_prefix}-{i + 1:02d}",
            short_review="좋았어요" if with_memo else "",
        )


# ---------------------------------------------------------------------------
# filter=unofficial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnofficialFilter:
    """filter=unofficial keeps only 비공식 (personal_entry) records."""

    def test_first_page_five_unofficial(self, user_client, make_event):
        user, client = user_client()
        _make_unofficial_visits(user, 7)
        _make_official_visits(user, make_event, 3)

        resp = client.get("/archive/visits/?filter=unofficial")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert len(page_obj.object_list) == 5

    def test_second_page_two_unofficial(self, user_client, make_event):
        user, client = user_client()
        _make_unofficial_visits(user, 7)
        _make_official_visits(user, make_event, 3)

        resp = client.get("/archive/visits/?filter=unofficial&page=2")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.number == 2
        assert len(page_obj.object_list) == 2

    def test_no_official_rows_leak_through_filter(self, user_client, make_event):
        user, client = user_client()
        _make_unofficial_visits(user, 3)
        _make_official_visits(user, make_event, 2)

        resp = client.get("/archive/visits/?filter=unofficial")

        visit_rows = resp.context["visit_rows"]
        for row in visit_rows:
            assert row["subject"]["is_official"] is False

    def test_summary_counts_reflect_total_all_records(self, user_client, make_event):
        """total_count and memo_count always count ALL records, not just filtered."""
        user, client = user_client()
        _make_unofficial_visits(user, 7, with_memo=True)
        _make_official_visits(user, make_event, 3, with_memo=True)

        resp = client.get("/archive/visits/?filter=unofficial")

        assert resp.context["total_count"] == 10
        assert resp.context["memo_count"] == 10

    def test_selected_filter_in_context(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/?filter=unofficial")

        assert resp.context["selected_filter"] == "unofficial"

    def test_no_filter_selected_filter_is_empty_string(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/")

        assert resp.context["selected_filter"] == ""


# ---------------------------------------------------------------------------
# filter=cat:<label>
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCategoryFilter:
    """filter=cat:<label> OR-matches official (by code) and unofficial (by label)."""

    def test_cat_filter_matches_official_and_unofficial(self, user_client, make_event):
        user, client = user_client()
        # 2 official events with popup_store → CATEGORY_LABELS["popup_store"] = "팝업스토어"
        _make_official_visits(user, make_event, 2, category="popup_store")
        # 2 unofficial with same label "팝업스토어"
        _make_unofficial_visits(user, 2, category="팝업스토어")
        # 1 other category — must not appear
        other_ev = make_event(title="콜라보 행사", category="collaboration_cafe")
        VisitRecord.objects.create(user=user, event=other_ev, visited_on="2026-03-01")

        resp = client.get("/archive/visits/?filter=cat:팝업스토어")

        assert resp.status_code == 200
        assert resp.context["page_obj"].paginator.count == 4

    def test_cat_filter_excludes_non_matching_records(self, user_client, make_event):
        user, client = user_client()
        _make_official_visits(user, make_event, 3, category="popup_store")
        other_ev = make_event(title="콜라보", category="collaboration_cafe")
        VisitRecord.objects.create(user=user, event=other_ev, visited_on="2026-04-01")

        resp = client.get("/archive/visits/?filter=cat:팝업스토어")

        visit_rows = resp.context["visit_rows"]
        for row in visit_rows:
            label = row["subject"]["category_label"]
            assert label == "팝업스토어"

    def test_cat_filter_selected_filter_in_context(self, user_client, make_event):
        user, client = user_client()
        ev = make_event(title="팝업 행사", category="popup_store")
        VisitRecord.objects.create(user=user, event=ev, visited_on="2026-06-01")

        resp = client.get("/archive/visits/?filter=cat:팝업스토어")

        assert resp.context["selected_filter"] == "cat:팝업스토어"


# ---------------------------------------------------------------------------
# Bad filter values → fallback (200, no filter)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBadFilterFallback:
    """Unrecognised filter values never raise 500 and silently fall back."""

    def test_unknown_filter_slug_falls_back_to_all(self, user_client, make_event):
        user, client = user_client()
        _make_official_visits(user, make_event, 3)

        resp = client.get("/archive/visits/?filter=nonexistent")

        assert resp.status_code == 200
        assert resp.context["selected_filter"] == ""
        assert resp.context["page_obj"].paginator.count == 3

    def test_cat_with_empty_label_falls_back(self, user_client, make_event):
        user, client = user_client()
        _make_official_visits(user, make_event, 2)

        resp = client.get("/archive/visits/?filter=cat:")

        assert resp.status_code == 200
        assert resp.context["selected_filter"] == ""
        assert resp.context["page_obj"].paginator.count == 2

    def test_cat_with_unlisted_label_falls_back(self, user_client, make_event):
        """A cat: label not in the whitelist derived from user's own data falls back."""
        user, client = user_client()
        ev = make_event(title="팝업", category="popup_store")
        VisitRecord.objects.create(user=user, event=ev, visited_on="2026-06-01")

        resp = client.get("/archive/visits/?filter=cat:없는라벨")

        assert resp.status_code == 200
        assert resp.context["selected_filter"] == ""
        assert resp.context["page_obj"].paginator.count == 1


# ---------------------------------------------------------------------------
# categories and has_unofficial from FULL data (not just current page)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCategoriesFromFullData:
    """categories chip list and has_unofficial must reflect ALL records."""

    def test_category_from_page2_still_appears_in_chip_list(self, user_client, make_event):
        user, client = user_client()
        # 5 popup records (newer) — fill page 1
        for i in range(5):
            ev = make_event(title=f"팝업{i}", category="popup_store")
            VisitRecord.objects.create(user=user, event=ev, visited_on=f"2026-06-{i + 1:02d}")
        # 1 collab_cafe record (older) — lands on page 2
        ev2 = make_event(title="콜라보 행사", category="collaboration_cafe")
        VisitRecord.objects.create(user=user, event=ev2, visited_on="2026-05-01")

        resp = client.get("/archive/visits/")

        categories = resp.context["categories"]
        assert "팝업스토어" in categories
        assert "콜라보 카페" in categories  # would be missing under old per-page logic

    def test_has_unofficial_true_even_when_unofficial_on_page2(self, user_client, make_event):
        user, client = user_client()
        # 5 official records (newer) → fill page 1
        for i in range(5):
            ev = make_event(title=f"공식{i}", category="popup_store")
            VisitRecord.objects.create(user=user, event=ev, visited_on=f"2026-06-{i + 1:02d}")
        # 1 unofficial record (older) → lands on page 2
        entry = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 카페", category="카페"
        )
        VisitRecord.objects.create(user=user, personal_entry=entry, visited_on="2026-05-01")

        resp = client.get("/archive/visits/")

        assert resp.context["has_unofficial"] is True

    def test_has_official_reflects_full_data(self, user_client, make_event):
        user, client = user_client()
        ev = make_event(title="공식 행사")
        VisitRecord.objects.create(user=user, event=ev, visited_on="2026-06-01")

        resp = client.get("/archive/visits/")

        assert resp.context["has_official"] is True

    def test_has_official_false_when_only_unofficial(self, user_client):
        user, client = user_client()
        entry = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="비공식"
        )
        VisitRecord.objects.create(user=user, personal_entry=entry, visited_on="2026-06-01")

        resp = client.get("/archive/visits/")

        assert resp.context["has_official"] is False


# ---------------------------------------------------------------------------
# pager_query preserves filter and q together
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVisitsPagerQuery:
    """pager_query carries filter and q params so paging never drops them."""

    def test_pager_preserves_unofficial_filter(self, user_client):
        user, client = user_client()
        _make_unofficial_visits(user, 7)  # 2 pages

        resp = client.get("/archive/visits/?filter=unofficial")

        pager_query = resp.context["pager_query"]
        assert "filter=unofficial" in pager_query
        assert b"page=2" in resp.content  # pager renders a page-2 link

    def test_pager_preserves_filter_and_q_together(self, user_client):
        user, client = user_client()
        _make_unofficial_visits(user, 7)

        resp = client.get("/archive/visits/?filter=unofficial&q=abc")

        assert resp.status_code == 200
        pager_query = resp.context["pager_query"]
        assert "filter=unofficial" in pager_query
        assert "q=abc" in pager_query

    def test_pager_query_empty_when_no_filter_no_q(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/")

        assert resp.context["pager_query"] == ""

    def test_pager_query_only_q_when_no_filter(self, user_client):
        user, client = user_client()
        _make_unofficial_visits(user, 7)

        resp = client.get("/archive/visits/?q=비공식")

        pager_query = resp.context["pager_query"]
        assert "q=" in pager_query
        assert "filter" not in pager_query
