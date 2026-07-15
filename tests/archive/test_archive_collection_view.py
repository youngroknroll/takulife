"""Tests for the collection list page (core.views.archive_collection_items).

Behavior under test (collection domain design plan §4 PR-C5b-2, CP-L1~L22):
- /archive/collection/ is login-gated, owner-scoped, and paginated at 10.
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


@pytest.mark.django_db
class TestArchiveCollectionViewAuth:
    def test_authenticated_user_gets_200(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/")

        assert resp.status_code == 200
        assert "core/archive/collection.html" in [t.name for t in resp.templates]

    def test_anonymous_user_redirected_to_login(self, client):
        resp = client.get("/archive/collection/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionSummary:
    def test_summary_counts_owner_scoped(self, user_client, make_user, make_collection_item):
        user, client = user_client()
        other = make_user()
        make_collection_item(user, name="내 보유품", is_wanted=False)
        make_collection_item(user, name="내 위시템", is_wanted=True)
        make_collection_item(other, name="남의 물건", is_wanted=False)

        resp = client.get("/archive/collection/")

        assert resp.context["owned_count"] == 1
        assert resp.context["wanted_count"] == 1


@pytest.mark.django_db
class TestArchiveCollectionListOwnerScope:
    def test_only_owner_items_listed(self, user_client, make_user, make_collection_item):
        user, client = user_client()
        other = make_user()
        make_collection_item(user, name="내 아이템")
        make_collection_item(other, name="남의 아이템")

        resp = client.get("/archive/collection/")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["내 아이템"]
        assert "남의 아이템".encode() not in resp.content


@pytest.mark.django_db
class TestArchiveCollectionPagination:
    def test_page_size_is_ten(self, user_client, make_collection_item):
        user, client = user_client()
        for i in range(11):
            make_collection_item(user, name=f"아이템{i:02d}")

        resp = client.get("/archive/collection/")
        page_obj = resp.context["page_obj"]

        assert ARCHIVE_COLLECTION_PAGE_SIZE == 10
        assert page_obj.paginator.count == 11
        assert len(page_obj.object_list) == 10

        resp2 = client.get("/archive/collection/?page=2")
        assert len(resp2.context["page_obj"].object_list) == 1


@pytest.mark.django_db
class TestArchiveCollectionSearch:
    def test_q_filters_by_name(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="유메 아크릴")
        make_collection_item(user, name="다른 굿즈")

        resp = client.get("/archive/collection/?q=유메")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["유메 아크릴"]


@pytest.mark.django_db
class TestArchiveCollectionIsWantedFilter:
    def test_is_wanted_true_narrows_to_wanted_only(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False)
        make_collection_item(user, name="구함템", is_wanted=True)

        resp = client.get("/archive/collection/?is_wanted=true")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["구함템"]

    def test_is_wanted_false_narrows_to_owned_only(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False)
        make_collection_item(user, name="구함템", is_wanted=True)

        resp = client.get("/archive/collection/?is_wanted=false")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["보유템"]

    @pytest.mark.parametrize("bad_value", ["", "ture", "1", "TRUE", "yes"])
    def test_unrecognised_is_wanted_values_apply_no_filter(
        self, user_client, make_collection_item, bad_value
    ):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False)
        make_collection_item(user, name="구함템", is_wanted=True)

        resp = client.get(f"/archive/collection/?is_wanted={bad_value}")

        names = {row["item"].name for row in resp.context["item_rows"]}
        assert names == {"보유템", "구함템"}

    def test_missing_is_wanted_param_applies_no_filter(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False)
        make_collection_item(user, name="구함템", is_wanted=True)

        resp = client.get("/archive/collection/")

        names = {row["item"].name for row in resp.context["item_rows"]}
        assert names == {"보유템", "구함템"}


@pytest.mark.django_db
class TestArchiveCollectionFilterOptions:
    def test_filter_values_populated_from_query_layer(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="A", work_title="WorkA", character_name="CharA", item_type="keyring")
        make_collection_item(user, name="B", work_title="WorkB", character_name="CharB", item_type="badge")

        resp = client.get("/archive/collection/")

        filter_values = resp.context["filter_values"]
        assert filter_values["work_title"] == ["WorkA", "WorkB"]
        assert filter_values["character_name"] == ["CharA", "CharB"]
        assert filter_values["item_type"] == ["badge", "keyring"]


@pytest.mark.django_db
class TestArchiveCollectionExactMatchFilters:
    def test_work_title_character_name_item_type_exact_match(self, user_client, make_collection_item):
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
            "/archive/collection/?work_title=WorkA&character_name=CharB&item_type=keyring"
        )

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["일치"]


@pytest.mark.django_db
class TestArchiveCollectionQueryStringHelpers:
    """CP-L11~L15: all 5 axes set simultaneously so a single-axis leak or
    omission cannot accidentally pass (verified via context, mirroring
    TestVisitsPagerQuery's substring-membership style — never parses hrefs)."""

    def _get_all_axes(self, user, client):
        # has_items must be True for the filter/search controls to render at
        # all (PO decision: an empty collection hides them entirely) — this
        # item deliberately does NOT match the filters below, only its mere
        # existence matters here.
        CollectionItem.objects.create(user=user, name="배경 아이템")
        return client.get(
            "/archive/collection/"
            "?q=abc&work_title=WorkA&character_name=CharB&item_type=keyring&is_wanted=true"
        )

    def test_chip_query_suffix_excludes_is_wanted(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        chip_query_suffix = resp.context["chip_query_suffix"]

        assert "q=abc" in chip_query_suffix
        assert "work_title=WorkA" in chip_query_suffix
        assert "character_name=CharB" in chip_query_suffix
        assert "item_type=keyring" in chip_query_suffix
        assert "is_wanted" not in chip_query_suffix

    def test_select_form_hidden_fields_are_q_and_is_wanted(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)

        assert b'name="q" value="abc"' in resp.content
        assert b'name="is_wanted" value="true"' in resp.content

    def test_search_form_hidden_fields_are_is_wanted_and_three_filters(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        content = resp.content

        assert b'name="is_wanted" value="true"' in content
        assert b'name="work_title" value="WorkA"' in content
        assert b'name="character_name" value="CharB"' in content
        assert b'name="item_type" value="keyring"' in content
        assert b"archive_search.js" in content

    def test_clear_query_suffix_excludes_q(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        clear_query_suffix = resp.context["clear_query_suffix"]

        assert "is_wanted=true" in clear_query_suffix
        assert "work_title=WorkA" in clear_query_suffix
        assert "character_name=CharB" in clear_query_suffix
        assert "item_type=keyring" in clear_query_suffix
        assert "q=abc" not in clear_query_suffix
        assert "q=" not in clear_query_suffix

    def test_pager_query_carries_all_five_axes(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        pager_query = resp.context["pager_query"]

        assert "q=abc" in pager_query
        assert "work_title=WorkA" in pager_query
        assert "character_name=CharB" in pager_query
        assert "item_type=keyring" in pager_query
        assert "is_wanted=true" in pager_query

    def test_pager_query_empty_when_no_filters_no_q(self, user_client, make_collection_item):
        user, client = user_client()
        for i in range(11):  # force a pager to exist
            make_collection_item(user, name=f"아이템{i:02d}")

        resp = client.get("/archive/collection/")

        assert resp.context["pager_query"] == ""


@pytest.mark.django_db
class TestArchiveCollectionPartial:
    def test_partial_renders_fragment_only(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/?partial=1")

        assert resp.status_code == 200
        names = {t.name for t in resp.templates if t.name}
        assert "core/partials/_archive_results_collection.html" in names
        assert "core/archive/collection.html" not in names
        assert "base.html" not in names
        assert b"<html" not in resp.content.lower()

    def test_partial_requires_login(self, client):
        resp = client.get("/archive/collection/?partial=1")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionEmptyStates:
    def test_no_items_hides_filter_controls(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/")
        content = resp.content

        assert b'class="archive-search"' not in content
        assert b'name="work_title"' not in content
        assert b'class="visit-filter"' not in content

    def test_filtered_zero_results_keeps_filter_controls(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템", is_wanted=False, work_title="WorkA")

        resp = client.get("/archive/collection/?work_title=NoMatch")

        assert resp.context["item_rows"] == []
        content = resp.content
        assert b'class="archive-search"' in content
        assert b'name="work_title"' in content

    def test_search_zero_results_keeps_filter_controls(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="보유템")

        resp = client.get("/archive/collection/?q=없는검색어")

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

    def test_owned_item_shows_quantity_tradeable_and_wanted_badges(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(
            user, name="A아이템", quantity=3, tradeable_quantity=2, is_wanted=True
        )

        resp = client.get("/archive/collection/?partial=1")
        row = resp.context["item_rows"][0]

        assert "수량 3개".encode() in resp.content
        assert "교환 가능 2개".encode() in resp.content
        assert "구함".encode() in resp.content
        assert row["quantity_label"] == "수량 3개"
        assert row["tradeable_label"] == "교환 가능 2개"

    def test_zero_quantity_item_shows_no_quantity_or_tradeable_or_wanted_badges(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(
            user, name="B아이템", quantity=0, tradeable_quantity=0, is_wanted=False
        )

        resp = client.get("/archive/collection/?partial=1")
        row = resp.context["item_rows"][0]

        assert "수량 0개".encode() not in resp.content
        assert "교환 가능".encode() not in resp.content
        assert "구함".encode() not in resp.content
        assert "보유 3개".encode() not in resp.content
        assert row["quantity_label"] == ""
        assert row["tradeable_label"] == ""


@pytest.mark.django_db
class TestArchiveCollectionNav:
    def test_independent_nav_group_added(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/")
        content = resp.content

        assert content.count(b'class="archive-nav-group"') == 3
        assert b'href="/archive/collection/"' in content
        assert b'href="/archive/collection/" class="active"' in content
        # The pre-existing "내 기록" group's 3 links stay intact.
        assert b'href="/archive/"' in content
        assert b'href="/archive/statuses/"' in content
        assert b'href="/archive/visits/"' in content
