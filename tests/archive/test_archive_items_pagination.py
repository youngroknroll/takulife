"""Tests for pagination and search on /archive/personal/ (비공식 personal entries).

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

pytestmark = pytest.mark.web


# ---------------------------------------------------------------------------
# Basic pagination
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsPagination:
    """7 items paginate at 5/page; page_obj is in the template context."""

    def test_개인_기록_7건을_등록하면_첫_페이지에_5건이_표시된다(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7)

        resp = client.get("/archive/personal/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert page_obj.paginator.num_pages == 2
        assert len(page_obj.object_list) == 5

    def test_개인_기록_7건_중_두번째_페이지를_조회하면_나머지_2건이_표시된다(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7)

        resp = client.get("/archive/personal/?page=2")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.number == 2
        assert len(page_obj.object_list) == 2

    def test_개인_기록이_5건_이하이면_페이지가_한_개만_생성된다(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 4)

        resp = client.get("/archive/personal/")

        assert resp.context["page_obj"].paginator.num_pages == 1


# ---------------------------------------------------------------------------
# Summary counts from ALL entries (not filtered/paginated subset)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsSummaryCounts:
    """Summary card counts are always unfiltered totals."""

    def test_요약_카운트는_개인_기록_전체_건수를_집계한다(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7, kind=PersonalEntry.Kind.PLACE)

        resp = client.get("/archive/personal/")

        assert resp.context["total_count"] == 7
        assert "place_count" not in resp.context
        assert "goods_count" not in resp.context

    def test_검색어로_목록을_좁혀도_요약_전체_건수는_변하지_않는다(self, user_client, make_entries):
        """total_count does not shrink when q narrows entry_rows."""
        user, client = user_client()
        make_entries(user, 7, kind=PersonalEntry.Kind.PLACE, title_prefix="항목")

        # q="00" would match only "항목 00"
        resp = client.get("/archive/personal/?q=00")

        # Summary must still report 7, not the filtered count
        assert resp.context["total_count"] == 7

    def test_검색_결과가_0건이어도_기록_보유_여부는_true로_유지된다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="내 항목")

        resp = client.get("/archive/personal/?q=없는검색어XYZ")

        assert resp.status_code == 200
        assert resp.context["has_entries"] is True  # 1 entry exists regardless


# ---------------------------------------------------------------------------
# q search on /archive/personal/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsSearch:
    """?q= filters entry_rows on /archive/personal/."""

    def test_검색어로_필터링하면_제목이_일치하는_기록만_표시된다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="매칭 항목")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="다른 항목")

        resp = client.get("/archive/personal/?q=매칭")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "매칭 항목" in titles
        assert "다른 항목" not in titles

    def test_검색어로_필터링하면_페이지네이터_건수도_검색_결과_기준으로_줄어든다(self, user_client, make_entry):
        """page_obj.paginator.count reflects the filtered (q-narrowed) count."""
        user, client = user_client()
        for i in range(3):
            make_entry(user, kind=PersonalEntry.Kind.PLACE, title=f"매칭{i}")
        for i in range(4):
            make_entry(user, kind=PersonalEntry.Kind.PLACE, title=f"기타{i}")

        resp = client.get("/archive/personal/?q=매칭")

        assert resp.context["page_obj"].paginator.count == 3

    def test_빈_검색어를_보내면_모든_기록이_표시된다(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 3)

        resp = client.get("/archive/personal/?q=")

        assert resp.context["page_obj"].paginator.count == 3
        assert resp.context["has_query"] is False


# ---------------------------------------------------------------------------
# Context keys: q, has_query, pager_query
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsContextKeys:
    """page_obj, q, has_query, pager_query must all be present in the context."""

    def test_검색어를_보내면_컨텍스트에_검색어와_검색_여부가_담긴다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/personal/?q=검색어")

        assert resp.context["q"] == "검색어"
        assert resp.context["has_query"] is True

    def test_검색어_파라미터가_없으면_컨텍스트의_검색어는_비어있고_검색_여부는_false다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/personal/")

        assert resp.context["q"] == ""
        assert resp.context["has_query"] is False

    def test_페이저_쿼리_문자열은_검색어를_포함한다(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7)  # 2 pages

        resp = client.get("/archive/personal/?q=항목")

        pager_query = resp.context["pager_query"]
        assert "q=" in pager_query

    def test_검색어가_없으면_페이저_쿼리_문자열은_비어있다(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 7)

        resp = client.get("/archive/personal/")

        assert resp.context["pager_query"] == ""

    def test_공백만_있는_검색어는_빈_검색어로_정규화된다(self, user_client, make_entries):
        user, client = user_client()
        make_entries(user, 3)

        resp = client.get("/archive/personal/?q=   ")

        assert resp.context["q"] == ""
        assert resp.context["has_query"] is False
        assert resp.context["page_obj"].paginator.count == 3

    def test_과도하게_긴_검색어를_보내도_서버_오류_없이_100자로_잘린다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/personal/?q=" + "Z" * 200)

        assert resp.status_code == 200
        assert len(resp.context["q"]) <= 100


# ---------------------------------------------------------------------------
# visit_linked_count + sort context (직접 등록 에디토리얼 plan Part 1 §5, PC)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveItemsVisitLinkedCountAndSort:
    def test_목록_뷰_컨텍스트에_방문_기록_연결_카운트가_담긴다(
        self, user_client, make_entry, make_visit
    ):
        user, client = user_client()
        linked = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P1")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P2")
        make_visit(user, personal_entry=linked, visited_on="2026-01-01")

        resp = client.get("/archive/personal/")

        assert resp.context["visit_linked_count"] == 1

    def test_정렬_파라미터를_보내면_페이저_쿼리에도_정렬이_유지된다(
        self, user_client, make_entries
    ):
        user, client = user_client()
        make_entries(user, 7)  # 2 pages

        resp = client.get("/archive/personal/?sort=oldest")

        assert resp.context["pager_query"] == "&sort=oldest"
        assert resp.context["page_obj"].number == 1

    def test_검색어와_정렬을_함께_보내면_페이저_쿼리에_둘_다_유지된다(
        self, user_client, make_entries
    ):
        user, client = user_client()
        make_entries(user, 7, title_prefix="항목")

        resp = client.get("/archive/personal/?q=항목&sort=oldest")

        pager_query = resp.context["pager_query"]
        assert "q=" in pager_query
        assert "sort=oldest" in pager_query

    def test_목록_뷰_컨텍스트에_선택된_정렬과_라벨과_정렬_옵션이_담긴다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/personal/?sort=oldest")

        assert resp.context["selected_sort"] == "oldest"
        assert resp.context["selected_sort_label"] == "오래된 등록순"
        assert resp.context["ARCHIVE_PERSONAL_SORT"] == (
            ("", "최근 등록순"),
            ("oldest", "오래된 등록순"),
        )
