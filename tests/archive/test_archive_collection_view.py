"""Tests for the collection list page (core.views.archive_collection_items).

Behavior under test (collection domain design plan §4 PR-C5b-2, CP-L1~L22):
- /collection/ is login-gated, owner-scoped, and paginated at 10.
- q / is_wanted / work_title / character_name / item_type filter server-side,
  reusing list_user_collection_items / user_collection_item_filter_values /
  user_collection_item_summary_counts unchanged.
- Three query-string helpers carry different axis subsets (PO's cross-
  preservation warning): chip_query_suffix (q + 3 filters, is_wanted
  excluded), pager_query (all 5 axes), clear_query_suffix (is_wanted + 3
  filters, q excluded).
- Filter/search controls (chips, select form, search form) are hidden when
  the user owns zero items at all, but stay visible when a filter or search
  narrows an existing collection to zero results (PO decision 2026-07-16).
- ?partial=1 renders only the results fragment, gated by the same login
  requirement as the full page.
"""
import pytest

from archive.models import CollectionItem
from archive.queries import ARCHIVE_COLLECTION_PAGE_SIZE
from core.views import _collection_item_row, _series_ink_class

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveCollectionViewAuth:
    def test_인증된_사용자가_컬렉션_페이지에_접근하면_200과_함께_컬렉션_템플릿이_렌더링된다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/")

        assert resp.status_code == 200
        assert "core/archive/collection.html" in [t.name for t in resp.templates]

    def test_비로그인_사용자가_컬렉션_페이지에_접근하면_로그인_페이지로_리다이렉트된다(self, client):
        resp = client.get("/collection/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionSummary:
    def test_컬렉션_요약_카운트는_본인_소유_항목만_집계한다(self, user_client, make_user, make_collection_item):
        user, client = user_client()
        other = make_user()
        make_collection_item(user, name="내 보유품", is_wanted=False)
        make_collection_item(user, name="내 위시템", is_wanted=True)
        make_collection_item(other, name="남의 물건", is_wanted=False)

        resp = client.get("/collection/")

        assert resp.context["owned_count"] == 1
        assert resp.context["wanted_count"] == 1


@pytest.mark.django_db
class TestArchiveCollectionListOwnerScope:
    def test_컬렉션_목록에는_본인_소유_항목만_표시된다(self, user_client, make_user, make_collection_item):
        user, client = user_client()
        other = make_user()
        make_collection_item(user, name="내 아이템")
        make_collection_item(other, name="남의 아이템")

        resp = client.get("/collection/")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["내 아이템"]
        assert "남의 아이템".encode() not in resp.content


@pytest.mark.django_db
class TestArchiveCollectionPagination:
    def test_컬렉션_목록은_10개_단위로_페이지네이션된다(self, user_client, make_collection_item):
        user, client = user_client()
        for i in range(11):
            make_collection_item(user, name=f"아이템{i:02d}")

        resp = client.get("/collection/")
        page_obj = resp.context["page_obj"]

        assert ARCHIVE_COLLECTION_PAGE_SIZE == 10
        assert page_obj.paginator.count == 11
        assert len(page_obj.object_list) == 10

        resp2 = client.get("/collection/?page=2")
        assert len(resp2.context["page_obj"].object_list) == 1


@pytest.mark.django_db
class TestArchiveCollectionSearch:
    def test_검색어로_컬렉션_목록을_필터링하면_이름이_일치하는_항목만_표시된다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="유메 아크릴")
        make_collection_item(user, name="다른 굿즈")

        resp = client.get("/collection/?q=유메")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["유메 아크릴"]


@pytest.mark.django_db
class TestArchiveCollectionIsWantedFilter:
    def test_구함_필터를_true로_지정하면_구하는_항목만_표시된다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False)
        make_collection_item(user, name="구함템", is_wanted=True)

        resp = client.get("/collection/?is_wanted=true")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["구함템"]

    def test_구함_필터를_false로_지정하면_보유한_항목만_표시된다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False)
        make_collection_item(user, name="구함템", is_wanted=True)

        resp = client.get("/collection/?is_wanted=false")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["보유템"]

    @pytest.mark.parametrize(
        "bad_value",
        ["", "ture", "1", "TRUE", "yes"],
        ids=["빈값", "오타", "숫자문자열", "대문자", "예_문자열"],
    )
    def test_구함_필터에_인식할_수_없는_값을_보내면_필터가_적용되지_않는다(
        self, user_client, make_collection_item, bad_value
    ):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False)
        make_collection_item(user, name="구함템", is_wanted=True)

        resp = client.get(f"/collection/?is_wanted={bad_value}")

        names = {row["item"].name for row in resp.context["item_rows"]}
        assert names == {"보유템", "구함템"}

    def test_구함_필터_파라미터가_없으면_필터가_적용되지_않는다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False)
        make_collection_item(user, name="구함템", is_wanted=True)

        resp = client.get("/collection/")

        names = {row["item"].name for row in resp.context["item_rows"]}
        assert names == {"보유템", "구함템"}


@pytest.mark.django_db
class TestArchiveCollectionFilterOptions:
    def test_필터_선택지는_쿼리_계층에서_계산된_값으로_채워진다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="A", work_title="WorkA", character_name="CharA", item_type="keyring")
        make_collection_item(user, name="B", work_title="WorkB", character_name="CharB", item_type="badge")

        resp = client.get("/collection/")

        filter_values = resp.context["filter_values"]
        assert filter_values["work_title"] == ["WorkA", "WorkB"]
        assert filter_values["character_name"] == ["CharA", "CharB"]
        assert filter_values["item_type"] == ["badge", "keyring"]


@pytest.mark.django_db
class TestArchiveCollectionExactMatchFilters:
    def test_작품명_캐릭터명_굿즈유형을_동시에_지정하면_모두_일치하는_항목만_표시된다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(
            user, name="일치", work_title="WorkA", character_name="CharB", item_type="keyring"
        )
        # Non-matching rows on each axis must never leak through.
        make_collection_item(
            user, name="다른작품", work_title="WorkX", character_name="CharB", item_type="keyring"
        )
        make_collection_item(
            user, name="다른캐릭터", work_title="WorkA", character_name="CharX", item_type="keyring"
        )
        make_collection_item(
            user, name="다른유형", work_title="WorkA", character_name="CharB", item_type="badge"
        )

        resp = client.get(
            "/collection/?work_title=WorkA&character_name=CharB&item_type=keyring"
        )

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["일치"]


@pytest.mark.django_db
class TestArchiveCollectionQueryStringHelpers:
    """CP-L11~L15: all 5 axes set simultaneously so a single-axis leak or
    omission cannot accidentally pass (verified via context, mirroring
    TestVisitsPagerQuery's substring-membership style — never parses hrefs)."""

    def _get_all_axes(self, user, client, extra=""):
        # has_items must be True for the filter/search controls to render at
        # all (PO decision: an empty collection hides them entirely) — this
        # item deliberately does NOT match the filters below, only its mere
        # existence matters here.
        CollectionItem.objects.create(user=user, name="배경 아이템")
        return client.get(
            "/collection/"
            "?q=abc&work_title=WorkA&character_name=CharB&item_type=keyring&is_wanted=true"
            f"{extra}"
        )

    def test_칩_쿼리_문자열은_구함_필터를_제외한_나머지_축을_포함한다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        chip_query_suffix = resp.context["chip_query_suffix"]

        assert "q=abc" in chip_query_suffix
        assert "work_title=WorkA" in chip_query_suffix
        assert "character_name=CharB" in chip_query_suffix
        assert "item_type=keyring" in chip_query_suffix
        assert "is_wanted" not in chip_query_suffix

    def test_검색_폼의_숨김_필드는_목록_보기모드를_담는다(self, user_client):
        """The 3-select filter form that used to carry these axes is gone
        (2026-07-23 에디토리얼 리빌드); the search form is now the only form on
        the page, so it must carry view= itself — otherwise searching from the
        목록 뷰 silently drops the user back to 갤러리."""
        user, client = user_client()

        resp = self._get_all_axes(user, client, extra="&view=list")

        assert b'name="view" value="list"' in resp.content

    def test_갤러리_보기모드에서는_검색_폼에_보기모드_숨김_필드가_없다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)

        assert b'name="view"' not in resp.content

    def test_검색_폼의_숨김_필드는_구함_필터와_세_필터값을_담는다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        content = resp.content

        assert b'name="is_wanted" value="true"' in content
        assert b'name="work_title" value="WorkA"' in content
        assert b'name="character_name" value="CharB"' in content
        assert b'name="item_type" value="keyring"' in content
        assert b"archive_search.js" in content

    def test_초기화_쿼리_문자열은_검색어를_제외한_나머지_축을_포함한다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        clear_query_suffix = resp.context["clear_query_suffix"]

        assert "is_wanted=true" in clear_query_suffix
        assert "work_title=WorkA" in clear_query_suffix
        assert "character_name=CharB" in clear_query_suffix
        assert "item_type=keyring" in clear_query_suffix
        assert "q=abc" not in clear_query_suffix
        assert "q=" not in clear_query_suffix

    def test_페이저_쿼리_문자열은_다섯_축을_모두_포함한다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        pager_query = resp.context["pager_query"]

        assert "q=abc" in pager_query
        assert "work_title=WorkA" in pager_query
        assert "character_name=CharB" in pager_query
        assert "item_type=keyring" in pager_query
        assert "is_wanted=true" in pager_query

    def test_필터와_검색어가_없으면_페이저_쿼리_문자열은_비어있다(self, user_client, make_collection_item):
        user, client = user_client()
        for i in range(11):  # force a pager to exist
            make_collection_item(user, name=f"아이템{i:02d}")

        resp = client.get("/collection/")

        assert resp.context["pager_query"] == ""


@pytest.mark.django_db
class TestArchiveCollectionPartial:
    def test_partial_요청을_보내면_결과_조각_템플릿만_렌더링된다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/?partial=1")

        assert resp.status_code == 200
        names = {t.name for t in resp.templates if t.name}
        assert "core/partials/_archive_results_collection.html" in names
        assert "core/archive/collection.html" not in names
        assert "base.html" not in names
        assert b"<html" not in resp.content.lower()

    def test_비로그인_사용자가_partial_요청을_보내면_로그인_페이지로_리다이렉트된다(self, client):
        resp = client.get("/collection/?partial=1")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionEmptyStates:
    def test_보유_항목이_전혀_없으면_검색_필터_컨트롤이_숨겨진다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/")
        content = resp.content

        assert b'class="archive-search"' not in content
        assert b'name="work_title"' not in content
        assert b'class="visit-filter"' not in content

    def test_필터_결과가_0건이어도_검색_필터_컨트롤은_유지된다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False, work_title="WorkA")

        resp = client.get("/collection/?work_title=NoMatch")

        assert resp.context["item_rows"] == []
        content = resp.content
        assert b'class="archive-search"' in content
        assert b'name="work_title"' in content

    def test_검색_결과가_0건이어도_검색_필터_컨트롤은_유지된다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템")

        resp = client.get("/collection/?q=없는검색어")

        assert resp.context["item_rows"] == []
        content = resp.content
        assert b'class="archive-search"' in content


@pytest.mark.django_db
class TestArchiveCollectionCardBadges:
    """quantity_label/tradeable_label assertions read resp.context — the
    view assembles those label strings itself (the fixture only sets the
    numeric quantity/tradeable_quantity, never the string), so this is not
    tautological for them.

    The is_wanted "구함" badge needs a different check. The literal text
    "구함" ALSO appears in the page's summary card label and in the
    is_wanted filter chip (both in collection.html, independent of any one
    item's own flag) — a raw full-page content search for "구함" would pass
    even if the item card itself never rendered a badge, and checking
    resp.context["item_rows"][...]["is_wanted"] only proves the fixture's
    own value round-trips through the view, not that the template renders
    anything with it. This was caught in review: an earlier version of this
    test used the context check and stayed green even when the badge's
    {% if %} in _archive_results_collection.html was hard-disabled
    (verified via a manual mutation round-trip).

    The fix: ?partial=1 renders ONLY _archive_results_collection.html
    (CP-L16/L17) — no summary card, no filter chips — so within that
    fragment "구함" can only come from the item badge itself, making the
    check a real rendering assertion. Do not revert this to a full-page
    request "for consistency" with the other assertions in this class —
    the collision is real and full-page content checks for "구함" are
    unreliable regardless of what fixture data is present.
    """

    def test_보유_항목_카드에는_수량_교환가능_구함_배지가_표시된다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(
            user, name="A아이템", quantity=3, tradeable_quantity=2, is_wanted=True
        )

        resp = client.get("/collection/?partial=1")
        row = resp.context["item_rows"][0]

        assert "수량 3개".encode() in resp.content
        assert "교환 가능 2개".encode() in resp.content
        assert "구함".encode() in resp.content
        assert row["quantity_label"] == "수량 3개"
        assert row["tradeable_label"] == "교환 가능 2개"

    def test_수량이_0인_항목_카드에는_수량_교환가능_구함_배지가_표시되지_않는다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(
            user, name="B아이템", quantity=0, tradeable_quantity=0, is_wanted=False
        )

        resp = client.get("/collection/?partial=1")
        row = resp.context["item_rows"][0]

        assert "수량 0개".encode() not in resp.content
        assert "교환 가능".encode() not in resp.content
        assert "구함".encode() not in resp.content
        assert "보유 3개".encode() not in resp.content
        assert row["quantity_label"] == ""
        assert row["tradeable_label"] == ""


@pytest.mark.django_db
class TestArchiveCollectionNav:
    """Target IA plan D1/§7-a-2 (.docs/plans/2026-07-16-target-ia-plan.md):
    the collection page is now a top-level destination, not an Activity
    sub-page — it must never render the Activity sub-nav tab bar (that
    structure's own contents, an always-visible tab bar since the 2026-07-21
    리디자인 ④단계 §B markup swap, are locked separately in
    tests/archive/test_archive_nav.py, exercised via an archive page that
    still includes it)."""

    def test_컬렉션_페이지에는_아카이브_내비게이션_탭바가_렌더링되지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/")
        content = resp.content

        assert '내 활동 하위 메뉴'.encode() not in content
        assert b'class="archive-nav-wrap"' not in content
        assert b'class="archive-nav-tabs"' not in content
        assert b'class="sub-nav"' not in content


@pytest.mark.django_db
class TestArchiveCollectionDuplicateFilter:
    """?duplicate=true/false narrows on quantity, mirroring the existing
    is_wanted fallback discipline (unrecognised/missing value = no filter,
    never a 500)."""

    def test_중복_필터를_true로_지정하면_수량_2개_이상인_항목만_표시된다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(user, name="중복템", quantity=2)
        make_collection_item(user, name="단일템", quantity=1)

        resp = client.get("/collection/?duplicate=true")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["중복템"]

    @pytest.mark.parametrize(
        "bad_value",
        ["", "maybe", "1"],
        ids=["빈값", "오타", "숫자문자열"],
    )
    def test_중복_필터에_인식할_수_없는_값을_보내면_필터가_적용되지_않는다(
        self, user_client, make_collection_item, bad_value
    ):
        user, client = user_client()
        make_collection_item(user, name="중복템", quantity=2)
        make_collection_item(user, name="단일템", quantity=1)

        resp = client.get(f"/collection/?duplicate={bad_value}")

        names = {row["item"].name for row in resp.context["item_rows"]}
        assert names == {"중복템", "단일템"}


@pytest.mark.django_db
class TestArchiveCollectionTradeableFilter:
    def test_교환가능_필터를_true로_지정하면_교환가능_수량이_1개_이상인_항목만_표시된다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(user, name="교환가능템", quantity=2, tradeable_quantity=1)
        make_collection_item(user, name="교환불가템", quantity=2, tradeable_quantity=0)

        resp = client.get("/collection/?tradeable=true")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["교환가능템"]

    @pytest.mark.parametrize(
        "bad_value",
        ["", "maybe", "1"],
        ids=["빈값", "오타", "숫자문자열"],
    )
    def test_교환가능_필터에_인식할_수_없는_값을_보내면_필터가_적용되지_않는다(
        self, user_client, make_collection_item, bad_value
    ):
        user, client = user_client()
        make_collection_item(user, name="교환가능템", quantity=2, tradeable_quantity=1)
        make_collection_item(user, name="교환불가템", quantity=2, tradeable_quantity=0)

        resp = client.get(f"/collection/?tradeable={bad_value}")

        names = {row["item"].name for row in resp.context["item_rows"]}
        assert names == {"교환가능템", "교환불가템"}


@pytest.mark.django_db
class TestArchiveCollectionViewMode:
    def test_view가_list이면_컨텍스트의_view_mode는_list이다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/?view=list")

        assert resp.context["view_mode"] == "list"

    def test_view_파라미터가_없으면_컨텍스트의_view_mode는_gallery이다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/")

        assert resp.context["view_mode"] == "gallery"

    def test_view에_인식할_수_없는_값을_보내면_view_mode는_gallery로_폴백된다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/?view=grid")

        assert resp.context["view_mode"] == "gallery"


@pytest.mark.django_db
class TestArchiveCollectionQueryStringHelpersV2:
    """Extends TestArchiveCollectionQueryStringHelpers for the collection
    리디자인's new axes: view/duplicate/tradeable.

    is_wanted/duplicate/tradeable are mutually-exclusive 서브탭 axes (a
    single active sub-tab swaps between them), so all three must be
    EXCLUDED from chip_query_suffix (chips only ever add work_title/
    character_name/item_type/q/view on top of whichever sub-tab is
    already active) but INCLUDED in pager_query and clear_query_suffix.
    """

    def _get_all_axes(self, user, client):
        # has_items must be True for the filter/search controls to render at
        # all (PO decision: an empty collection hides them entirely).
        CollectionItem.objects.create(user=user, name="배경 아이템")
        return client.get(
            "/collection/"
            "?q=abc&work_title=WorkA&character_name=CharB&item_type=keyring"
            "&is_wanted=true&duplicate=true&tradeable=true&view=list"
        )

    def test_보기모드는_칩_쿼리_문자열에_보존된다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)

        assert "view=list" in resp.context["chip_query_suffix"]

    def test_보기모드는_페이저_쿼리_문자열에_보존된다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)

        assert "view=list" in resp.context["pager_query"]

    def test_보기모드는_초기화_쿼리_문자열에_보존된다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)

        assert "view=list" in resp.context["clear_query_suffix"]

    def test_중복_교환가능_필터는_칩_쿼리_문자열에서_제외된다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        chip_query_suffix = resp.context["chip_query_suffix"]

        assert "duplicate" not in chip_query_suffix
        assert "tradeable" not in chip_query_suffix
        assert "is_wanted" not in chip_query_suffix

    def test_중복_교환가능_필터는_페이저와_초기화_쿼리_문자열에는_포함된다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        pager_query = resp.context["pager_query"]
        clear_query_suffix = resp.context["clear_query_suffix"]

        assert "duplicate=true" in pager_query
        assert "tradeable=true" in pager_query
        assert "is_wanted=true" in pager_query
        assert "duplicate=true" in clear_query_suffix
        assert "tradeable=true" in clear_query_suffix
        assert "is_wanted=true" in clear_query_suffix


@pytest.mark.django_db
class TestArchiveCollectionWorkTitleAndTradeableCounts:
    def test_컨텍스트에_교환가능_집계와_작품별_집계가_담긴다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(user, name="A", work_title="작품 A", tradeable_quantity=1, quantity=1)
        make_collection_item(user, name="B", work_title="작품 A", quantity=1)

        resp = client.get("/collection/")

        assert resp.context["tradeable_count"] == 1
        # The view carries the card's own series_ink_class onto each facet so
        # the sidebar dot matches the cards it filters to.
        assert resp.context["work_title_counts"] == [
            {"title": "작품 A", "count": 2, "series_ink_class": _series_ink_class("작품 A")}
        ]


@pytest.mark.django_db
class TestCollectionItemRowSeriesInkClass:
    """_collection_item_row()'s new series_ink_class assigns a deterministic
    accent-color bucket ("gi-1".."gi-6") per work_title, used by the
    리디자인's per-series color coding — "gi-0" is the explicit no-series
    bucket for a blank work_title."""

    def test_작품명이_같은_항목은_항상_같은_series_ink_class를_받는다(
        self, make_user, make_collection_item
    ):
        user = make_user(username="row-series-ink-consistent")
        first = make_collection_item(user, name="A1", work_title="작품 X")
        second = make_collection_item(user, name="A2", work_title="작품 X")

        first_row = _collection_item_row(first)
        second_row = _collection_item_row(second)

        assert first_row["series_ink_class"] == second_row["series_ink_class"]

    def test_series_ink_class는_gi_1부터_gi_6_사이의_값이다(
        self, make_user, make_collection_item
    ):
        user = make_user(username="row-series-ink-range")
        item = make_collection_item(user, name="A1", work_title="작품 Y")

        row = _collection_item_row(item)

        assert row["series_ink_class"] in {f"gi-{i}" for i in range(1, 7)}

    def test_작품명이_비어있으면_series_ink_class는_gi_0이다(
        self, make_user, make_collection_item
    ):
        user = make_user(username="row-series-ink-blank")
        item = make_collection_item(user, name="A1", work_title="")

        row = _collection_item_row(item)

        assert row["series_ink_class"] == "gi-0"
