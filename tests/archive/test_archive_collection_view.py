"""컬렉션 목록 페이지(core.views.archive_collection_items) 테스트.

검증 대상 동작(컬렉션 도메인 설계 계획 §4 PR-C5b-2, CP-L1~L22):
- /collection/ 은 로그인 필수, 소유자 범위, 10개 단위 페이지네이션.
- q / is_wanted / work_title / character_name / item_type 는 서버에서
  필터링하며 list_user_collection_items / user_collection_item_filter_values
  / user_collection_item_summary_counts 를 그대로 재사용한다.
- 쿼리스트링 헬퍼 3종은 서로 다른 축 부분집합을 담는다(PO의 교차 보존
  경고): chip_query_suffix(q + 필터 3종, is_wanted 제외), pager_query
  (5축 전부), clear_query_suffix(is_wanted + 필터 3종, q 제외).
- 필터/검색 컨트롤(칩, 셀렉트 폼, 검색 폼)은 사용자가 항목을 하나도
  보유하지 않을 때만 숨겨지고, 필터·검색이 결과를 0건으로 좁혀도 계속
  표시된다(PO 결정 2026-07-16).
- ?partial=1 은 결과 프래그먼트만 렌더하며 전체 페이지와 동일한 로그인
  요구를 따른다.
"""
import pytest

from archive.models import CollectionItem
from archive.queries import ARCHIVE_COLLECTION_PAGE_SIZE
from core.views.collection import _collection_item_row, _series_ink_classes

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
        make_collection_item(user, name="내 위시템", is_wanted=True, quantity=0)
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

    # test_구함_필터를_false로_지정하면_보유한_항목만_표시된다 삭제됨
    # (2026-07-28): ?is_wanted=false는 이제 ?owned=true로 302 리다이렉트되어
    # (레거시 북마크 호환, 아래 TestArchiveCollectionOwnedRedirect 참고)
    # /collection/?is_wanted=false 직접 GET은 더 이상 200 필터링 페이지를
    # 렌더하지 않는다. list_user_collection_items(user, is_wanted=False)의
    # 필터 동작 자체는 쿼리 계층에서 여전히 가드된다
    # (test_archive_queries.py::test_구함_필터_False는_구함이_아닌_항목만_반환한다)
    # DRF API 경계도 마찬가지다
    # (test_collection_items_api.py::test_구함_필터를_false로_보내면_API에서는_리다이렉트_없이_보유_항목만_반환된다).

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
class TestArchiveCollectionOwnedFilter:
    def test_보유_필터를_true로_지정하면_보유한_항목만_표시된다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="가진 것", quantity=3)
        make_collection_item(user, name="안 가진 것", quantity=0)

        resp = client.get("/collection/?owned=true")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["가진 것"]

    def test_보유_필터를_false로_지정하면_미보유_항목만_표시된다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="가진 것", quantity=3)
        make_collection_item(user, name="안 가진 것", quantity=0)

        resp = client.get("/collection/?owned=false")

        names = [row["item"].name for row in resp.context["item_rows"]]
        assert names == ["안 가진 것"]

    @pytest.mark.parametrize(
        "bad_value",
        ["", "ture", "1", "TRUE", "yes"],
        ids=["빈값", "오타", "숫자문자열", "대문자", "예_문자열"],
    )
    def test_보유_필터에_인식할_수_없는_값을_보내면_필터가_적용되지_않는다(
        self, user_client, make_collection_item, bad_value
    ):
        user, client = user_client()
        make_collection_item(user, name="가진 것", quantity=3)
        make_collection_item(user, name="안 가진 것", quantity=0)

        resp = client.get(f"/collection/?owned={bad_value}")

        names = {row["item"].name for row in resp.context["item_rows"]}
        assert names == {"가진 것", "안 가진 것"}

    def test_보유_필터_파라미터가_없으면_필터가_적용되지_않는다(self, user_client, make_collection_item):
        user, client = user_client()
        make_collection_item(user, name="가진 것", quantity=3)
        make_collection_item(user, name="안 가진 것", quantity=0)

        resp = client.get("/collection/")

        names = {row["item"].name for row in resp.context["item_rows"]}
        assert names == {"가진 것", "안 가진 것"}


@pytest.mark.django_db
class TestArchiveCollectionOwnedRedirect:
    """레거시 북마크 호환: `?is_wanted=false`가 예전엔 보유 탭 URL 자체였다.
    이제 보유(owned)가 독립 축이 되어(Cycle 2-B), 북마크된
    `?is_wanted=false` 링크는 `?owned=true`로 전달되어야 과소 집계
    (보유+구함 동시 행이 예전엔 빠졌다)를 멈추고 올바른 서브탭이 활성화된다.
    웹 페이지 한정 — DRF API(/api/collection-items/?is_wanted=false)는
    is_wanted 원래 의미를 유지하며 이 리다이렉트의 영향을 받지 않는다.

    `?is_wanted=false&owned=...` 정책(앱 내 링크로는 도달 불가, URL을 직접
    조합해야만 발생): 쿼리스트링에 `owned`가 이미 있으면 리다이렉트를
    건너뛴다 — 명시적 `owned` 값은 호출자가 새 축에서 이미 의도적으로
    선택했다는 뜻이므로, 이 레거시 호환 장치가 그 값을 덮어써서는 안 된다.
    """

    def test_구_보유_탭_URL은_새_보유_필터로_리다이렉트된다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/?is_wanted=false")

        assert resp.status_code == 302
        assert resp.url == "/collection/?owned=true"

    def test_리다이렉트는_다른_쿼리_파라미터를_보존한다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/?is_wanted=false&q=abc")

        assert resp.status_code == 302
        assert resp.url == "/collection/?q=abc&owned=true"

    def test_구함_탭_URL은_리다이렉트되지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/?is_wanted=true")

        assert resp.status_code == 200

    def test_파라미터가_없으면_리다이렉트되지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/")

        assert resp.status_code == 200

    def test_owned_파라미터가_이미_있으면_is_wanted_false여도_리다이렉트되지_않는다(
        self, user_client
    ):
        _, client = user_client()

        resp = client.get("/collection/?is_wanted=false&owned=false")

        assert resp.status_code == 200


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
        # 각 축에서 불일치하는 행이 새어 나오면 안 된다.
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
    """CP-L11~L15: 5개 축을 동시에 설정해 단일 축 누락/누출이 우연히
    통과하지 않도록 한다(컨텍스트로 검증, TestVisitsPagerQuery의 부분
    문자열 포함 방식을 따름 — href를 파싱하지 않는다)."""

    def _get_all_axes(self, user, client, extra=""):
        # has_items가 True여야 필터/검색 컨트롤이 렌더된다(PO 결정: 컬렉션이
        # 비어 있으면 전부 숨김) — 이 아이템은 의도적으로 아래 필터와
        # 불일치하며, 존재 자체만 의미가 있다.
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
        """이 축들을 담당하던 3-select 필터 폼은 사라졌다(2026-07-23 에디토리얼
        리빌드) — 이제 검색 폼이 페이지의 유일한 폼이므로 view=를 직접 담아야
        한다. 그러지 않으면 목록 뷰에서 검색할 때 조용히 갤러리로 되돌아간다."""
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
        for i in range(11):  # 페이저가 생기도록 한 쪽 분량을 넘긴다
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

        # 검색 입력의 접근 이름은 리네임과 무관하게 고정된다.
        assert b'name="work_title"' not in content
        assert "aria-label=\"컬렉션 검색\"".encode() not in content

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

    def test_어느_축에도_속하지_않는_등록_항목만_있어도_검색_필터_컨트롤은_유지된다(
        self, user_client, make_collection_item
    ):
        """세 축(quantity=0, is_wanted=False, tradeable_quantity=0) 모두에서
        벗어난 등록 행이라도 사용자가 등록한 항목은 있는 것이다 — has_items는
        True로 유지되어야 검색/필터 컨트롤이 잘못 숨겨지지 않는다."""
        user, client = user_client()
        make_collection_item(
            user, name="미분류행", quantity=0, is_wanted=False, tradeable_quantity=0
        )

        resp = client.get("/collection/")

        assert resp.context["has_items"] is True
        content = resp.content
        assert b'class="archive-search"' in content


@pytest.mark.django_db
class TestArchiveCollectionCardBadges:
    """quantity_label/tradeable_label 단언은 resp.context를 읽는다 — 뷰가 이
    라벨 문자열을 직접 조립하므로(픽스처는 숫자 quantity/tradeable_quantity만
    설정, 문자열은 안 줌) 이 부분은 동어반복이 아니다.

    is_wanted "구함" 배지는 다른 방식으로 검증해야 한다. "구함" 문자열은
    요약 카드 라벨과 is_wanted 필터 칩에도 등장하므로(둘 다 collection.html,
    개별 아이템 플래그와 무관) 전체 페이지에서 "구함"을 찾는 단언은 배지가
    아예 렌더되지 않아도 통과해버린다. context의 is_wanted 값 확인도 픽스처
    값이 뷰를 통과했다는 것만 증명할 뿐 템플릿이 실제로 그걸 렌더했다는
    증거는 아니다 — 검토 중 실제로 이 문제가 발견됐다: 이전 버전은 context
    검사만 했는데 _archive_results_collection.html의 배지 `{% if %}`를
    강제로 꺼도(수동 뮤테이션으로 실측) 계속 초록이었다.

    해결책: ?partial=1은 _archive_results_collection.html만 렌더하므로
    (CP-L16/L17, 요약 카드·필터 칩 없음) 이 프래그먼트 안의 "구함"은 오직
    아이템 배지에서만 나올 수 있어 실제 렌더링 검증이 된다. 이 클래스의 다른
    단언과 "일관성"을 맞춘다고 전체 페이지 요청으로 되돌리지 말 것 —
    충돌은 실제로 존재하며, 어떤 픽스처든 전체 페이지 "구함" 검색은
    신뢰할 수 없다.
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

    def test_보유_수량이_0이면_보유_톤_배지_없이_미보유_배지만_담긴다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(
            user, name="C아이템", quantity=0, tradeable_quantity=0, is_wanted=False
        )

        resp = client.get("/collection/?partial=1")
        row = resp.context["item_rows"][0]

        assert row["badges"] == [{"tone": "none", "label": "미보유"}]

    def test_교환가능_수량이_0이면_보유_수량이_양수여도_교환_톤_배지가_없다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(
            user, name="D아이템", quantity=3, tradeable_quantity=0, is_wanted=False
        )

        resp = client.get("/collection/?partial=1")
        row = resp.context["item_rows"][0]

        assert {"tone": "tradeable", "label": "교환"} not in row["badges"]


@pytest.mark.django_db
class TestArchiveCollectionNav:
    """Target IA 계획 D1/§7-a-2(.docs/plans/2026-07-16-target-ia-plan.md):
    컬렉션 페이지는 이제 최상위 목적지이지 활동 하위 페이지가 아니다 —
    활동 서브내비 탭바를 절대 렌더하지 않아야 한다(그 구조 자체는
    2026-07-21 리디자인 ④단계 §B 마크업 교체 이후 상시 노출 탭바이며,
    여전히 그걸 포함하는 아카이브 페이지를 통해 tests/archive/test_archive_nav.py
    에서 별도로 고정된다)."""

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
    """?duplicate=true/false 는 수량 기준으로 좁힌다. 기존 is_wanted의
    폴백 규율을 그대로 따른다(인식 못 하거나 없는 값 = 필터 미적용, 500
    금지)."""

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
    """컬렉션 리디자인의 새 축(view/duplicate/tradeable)에 대해
    TestArchiveCollectionQueryStringHelpers를 확장한다.

    is_wanted/duplicate/tradeable는 상호 배타적인 서브탭 축이다(활성
    서브탭 하나가 이들 사이를 전환) — 따라서 셋 다 chip_query_suffix에서는
    제외되어야 하고(칩은 이미 활성화된 서브탭 위에 work_title/
    character_name/item_type/q/view만 얹는다) pager_query와
    clear_query_suffix에는 포함되어야 한다.
    """

    def _get_all_axes(self, user, client):
        # has_items가 True여야 필터/검색 컨트롤이 렌더된다(PO 결정: 컬렉션이
        # 비어 있으면 전부 숨김).
        CollectionItem.objects.create(user=user, name="배경 아이템")
        return client.get(
            "/collection/"
            "?q=abc&work_title=WorkA&character_name=CharB&item_type=keyring"
            "&is_wanted=true&duplicate=true&tradeable=true&owned=true&view=list"
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
        assert "owned" not in chip_query_suffix

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

    def test_보유_필터는_페이저와_초기화_쿼리_문자열에는_포함된다(self, user_client):
        user, client = user_client()

        resp = self._get_all_axes(user, client)
        pager_query = resp.context["pager_query"]
        clear_query_suffix = resp.context["clear_query_suffix"]

        assert "owned=true" in pager_query
        assert "owned=true" in clear_query_suffix


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
        # 뷰는 카드 자체의 series_ink_class를 각 facet에도 실어 사이드바
        # 점이 필터되는 카드와 일치하게 한다. work_title이 하나만 등록돼
        # 등록 순번의 첫 슬롯을 받는다.
        assert resp.context["work_title_counts"] == [
            {"title": "작품 A", "count": 2, "series_ink_class": "gi-1"}
        ]


@pytest.mark.django_db
class TestCollectionItemRowSeriesInkClass:
    """_collection_item_row()의 새 series_ink_class는 work_title별 강조색
    버킷("gi-1"~"gi-12")을 해시가 아니라 최초 등록 순번으로 배정한다.
    호출자가 _series_ink_classes()로 만든 {work_title: class} 맵을 넘긴다
    — "gi-0"은 work_title이 빈 경우를 위한 명시적 무작품 버킷이다."""

    def test_작품명이_같은_항목은_항상_같은_series_ink_class를_받는다(
        self, make_user, make_collection_item
    ):
        user = make_user(username="row-series-ink-consistent")
        first = make_collection_item(user, name="A1", work_title="작품 X")
        second = make_collection_item(user, name="A2", work_title="작품 X")
        series_ink_classes = _series_ink_classes(["작품 X"])

        first_row = _collection_item_row(first, series_ink_classes)
        second_row = _collection_item_row(second, series_ink_classes)

        assert first_row["series_ink_class"] == second_row["series_ink_class"]

    def test_작품명이_비어있으면_series_ink_class는_gi_0이다(
        self, make_user, make_collection_item
    ):
        user = make_user(username="row-series-ink-blank")
        item = make_collection_item(user, name="A1", work_title="")
        series_ink_classes = _series_ink_classes([])

        row = _collection_item_row(item, series_ink_classes)

        assert row["series_ink_class"] == "gi-0"


@pytest.mark.django_db
class TestSeriesInkClassesRegistrationOrder:
    """_series_ink_classes()는 색을 해시가 아니라 최초 등록 순번으로 배정한다
    — 이게 이 수정의 핵심이다: 해시 버킷이 6개뿐이라 작품이 4개만 되어도
    충돌이 났다(달빛 카페 / 굿즈 페스타가 실제로 같은 색을 받았다). 순번
    배정은 12개 버킷을 다 쓸 때까지 충돌이 없다."""

    def test_서로_다른_작품_12개는_전부_다른_series_ink_class를_받는다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        titles = [f"작품 {i:02d}" for i in range(12)]
        for title in titles:
            make_collection_item(user, name=title, work_title=title)

        resp = client.get("/collection/")

        classes = {facet["series_ink_class"] for facet in resp.context["work_title_counts"]}
        assert len(classes) == 12

    def test_새_작품이_등록되어도_기존_작품들의_series_ink_class는_바뀌지_않는다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(user, name="A", work_title="작품 A")
        make_collection_item(user, name="B", work_title="작품 B")
        make_collection_item(user, name="C", work_title="작품 C")

        before = {
            facet["title"]: facet["series_ink_class"]
            for facet in client.get("/collection/").context["work_title_counts"]
        }

        # 작품 D를 추가로 등록해 개수 기준 정렬이 흔들리게 만든다 — 이래도
        # 기존 3개 작품의 색은 그대로여야 한다 (등록 순번 기반이라).
        make_collection_item(user, name="D1", work_title="작품 D")
        make_collection_item(user, name="D2", work_title="작품 D")
        make_collection_item(user, name="D3", work_title="작품 D")

        after = {
            facet["title"]: facet["series_ink_class"]
            for facet in client.get("/collection/").context["work_title_counts"]
        }

        assert after["작품 A"] == before["작품 A"]
        assert after["작품 B"] == before["작품 B"]
        assert after["작품 C"] == before["작품 C"]

    def test_13번째로_등록된_작품은_1번째와_같은_series_ink_class로_순환한다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        titles = [f"작품 {i:02d}" for i in range(13)]
        for title in titles:
            make_collection_item(user, name=title, work_title=title)

        resp = client.get("/collection/")

        facets = {facet["title"]: facet["series_ink_class"] for facet in resp.context["work_title_counts"]}
        assert facets["작품 00"] == "gi-1"
        assert facets["작품 12"] == "gi-1"

    def test_사이드바_작품별_집계의_색과_카드의_색은_일치한다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(user, name="A1", work_title="작품 A")
        make_collection_item(user, name="B1", work_title="작품 B")

        resp = client.get("/collection/")

        facet_classes = {
            facet["title"]: facet["series_ink_class"] for facet in resp.context["work_title_counts"]
        }
        for row in resp.context["item_rows"]:
            item = row["item"]
            if item.work_title:
                assert row["series_ink_class"] == facet_classes[item.work_title]


@pytest.mark.django_db
class TestSeriesInkClassesWholeCollectionPalette:
    """회귀 가드: 팔레트가 '전체 컬렉션' 기준이어야 한다는 계약을 필터/검색/
    페이지/partial 각 경로에서 개별적으로 고정한다. 기존 테스트는 전부
    무필터 client.get("/collection/") 뿐이라, 다음 편집자가 "쿼리 하나
    아끼자"며 팔레트를 filtered_qs 나 page_obj.object_list 에서 만들어도
    기존 테스트는 통과해버린다 — 그러면 같은 작품의 색이 검색/필터/페이지
    마다 달라지는데 아무 테스트도 못 잡는다."""

    def test_구함_필터를_걸어도_작품_색은_무필터_기준과_같다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(user, name="A1", work_title="작품 A", is_wanted=False)
        make_collection_item(user, name="B1", work_title="작품 B", is_wanted=True)
        make_collection_item(user, name="C1", work_title="작품 C", is_wanted=False)

        baseline = {
            facet["title"]: facet["series_ink_class"]
            for facet in client.get("/collection/").context["work_title_counts"]
        }

        filtered_resp = client.get("/collection/?is_wanted=true")
        for row in filtered_resp.context["item_rows"]:
            item = row["item"]
            assert row["series_ink_class"] == baseline[item.work_title]

    def test_검색어로_필터링해도_작품_색은_무필터_기준과_같다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        make_collection_item(user, name="굿즈 알파", work_title="작품 A")
        make_collection_item(user, name="굿즈 베타", work_title="작품 B")
        make_collection_item(user, name="굿즈 감마", work_title="작품 C")

        baseline = {
            facet["title"]: facet["series_ink_class"]
            for facet in client.get("/collection/").context["work_title_counts"]
        }

        searched_resp = client.get("/collection/?q=베타")
        for row in searched_resp.context["item_rows"]:
            item = row["item"]
            assert row["series_ink_class"] == baseline[item.work_title]

    def test_2페이지에만_있는_작품도_전체_기준_색을_받는다(
        self, user_client, make_collection_item
    ):
        user, client = user_client()
        assert ARCHIVE_COLLECTION_PAGE_SIZE == 10
        # 서로 다른 작품 11개. 목록은 -id(최신 등록 순)로 정렬되므로 가장
        # 먼저 등록한("작품 00", 가장 작은 id) 아이템이 가장 오래된 것으로
        # 밀려나 2페이지에만 등장한다.
        for i in range(11):
            make_collection_item(user, name=f"굿즈 {i:02d}", work_title=f"작품 {i:02d}")

        # work_title_counts 는 페이지와 무관하게 사용자 전체 컬렉션 기준이므로,
        # 1페이지 응답에서 이미 "작품 00"(2페이지 전용)의 기대 색을 얻을 수 있다.
        baseline_resp = client.get("/collection/")
        baseline = {
            facet["title"]: facet["series_ink_class"]
            for facet in baseline_resp.context["work_title_counts"]
        }
        assert "작품 00" in baseline

        page2_resp = client.get("/collection/?page=2")
        page2_titles = {row["item"].work_title: row["series_ink_class"] for row in page2_resp.context["item_rows"]}
        assert "작품 00" in page2_titles
        assert page2_titles["작품 00"] == baseline["작품 00"]

    def test_partial_프래그먼트도_전체_기준_색을_쓴다(
        self, user_client, make_collection_item
    ):
        # 작품 5개: 2개짜리 픽스처로는 "현재 페이지 기준으로 팔레트를 만드는"
        # 실수를 넣어도 두 경로가 우연히 같은 버킷에 떨어져 통과해버린다.
        # 검색 대상(작품 D)을 등록 순번 한가운데 두어 전체 기준과 결과 기준의
        # 순번이 반드시 달라지게 한다.
        user, client = user_client()
        for idx, title in enumerate(["작품 A", "작품 B", "작품 C", "작품 D", "작품 E"]):
            make_collection_item(user, name=f"굿즈 {idx}", work_title=title)

        baseline = {
            facet["title"]: facet["series_ink_class"]
            for facet in client.get("/collection/").context["work_title_counts"]
        }
        expected_class = baseline["작품 D"]

        partial_resp = client.get("/collection/?partial=1&q=굿즈 3")

        html = partial_resp.content.decode()
        assert f'class="gcard-work {expected_class}">작품 D</p>' in html

    def test_최초_등록_아이템_삭제는_알려진_한계로_작품_색_재배정을_유발한다(
        self, user_client, make_collection_item
    ):
        """Min(id) 기반 순번은 색을 DB에 저장하지 않는 트레이드오프의 대가로
        '최초 등록 아이템 삭제'에 취약하다는 알려진 한계를 그대로 고정한다
        (버그가 아니라 현재 계약의 문서화) — 작품(work_title)은 자유 입력
        문자열일 뿐 엔티티가 아니라서, 순수 표시용 색 때문에 스키마를
        늘리지 않기로 한 트레이드오프의 결과다. 등록(추가)에는 안정적이고
        (test_새_작품이_등록되어도... 로 보증), 삭제에는 취약하다.

        아래는 작품 2개짜리 최소 재현이라 두 작품이 서로 바뀌는 것으로 끝나지만,
        실제 컬렉션에서는 **한 번의 삭제가 2개보다 많은 작품의 색을 옮길 수
        있다** — 이르게 등록된 작품의 최초 아이템을 지우면 그 작품의 Min(id)가
        여러 작품을 한꺼번에 건너뛰기 때문이다."""
        user, client = user_client()
        a1 = make_collection_item(user, name="A1", work_title="작품 A")
        make_collection_item(user, name="B1", work_title="작품 B")
        make_collection_item(user, name="A2", work_title="작품 A")

        before = {
            facet["title"]: facet["series_ink_class"]
            for facet in client.get("/collection/").context["work_title_counts"]
        }
        # 등록 순번 0·1 은 SERIES_INK_STRIDE(=5) 만큼 떨어진 슬롯을 받는다
        # (색상환에서 150° 간격) — 인접 슬롯 gi-1/gi-2 가 아니다.
        assert before["작품 A"] == "gi-1"
        assert before["작품 B"] == "gi-6"

        # 작품 A의 최초 등록 아이템(A1)을 삭제하면, 작품 A의 Min(id)는 A2로
        # 밀려나 작품 B보다 뒤로 가고, 두 작품의 색이 서로 뒤바뀐다.
        a1.delete()

        after = {
            facet["title"]: facet["series_ink_class"]
            for facet in client.get("/collection/").context["work_title_counts"]
        }
        assert after["작품 A"] == "gi-6"
        assert after["작품 B"] == "gi-1"


@pytest.mark.django_db
class TestArchiveCollectionCardLinksToDetail:
    """CD-16 (컬렉션 상세 페이지 트랙): 목록 카드의 이름과 썸네일은 아직
    존재하지 않는 상세 라우트 `/collection/<id>/`로 연결되어야 한다 —
    prompt_plan.md의 컬렉션 상세 페이지 추가 항목에 대한 배선 회귀 가드다."""

    @pytest.mark.parametrize("view_mode", ["리스트", "갤러리"])
    def test_목록_카드의_이름과_이미지는_상세_페이지로_연결된다(
        self, user_client, make_collection_item, view_mode
    ):
        user, client = user_client()
        item = make_collection_item(user, name="상세연결굿즈")

        query = "?view=list" if view_mode == "리스트" else ""
        resp = client.get(f"/collection/{query}")

        # substring 단언(`in`)만으로는 이름 링크와 이미지 링크 중 하나만
        # 남아도(예: 썸네일/커버의 href 제거) 다른 하나가 여전히 그 문자열을
        # 포함해 통과한다 — 계획 §7의 "이름 + 이미지 둘 다 연결"의 절반이
        # 사라져도 초록이 되는 결함이다. 리스트는 `.collection-row-thumb` +
        # 이름 링크, 갤러리는 `.gcard-cover` + 이름 링크로 정확히 2개의
        # 동일 href가 나와야 하므로 등장 횟수를 센다. 클래스명 자체는
        # 단언하지 않아 프론트의 클래스 리네이밍에는 영향받지 않는다.
        detail_href = f'href="/collection/{item.pk}/"'.encode()
        content = resp.content
        assert content.count(detail_href) >= 2


@pytest.mark.django_db
class TestArchiveCollectionSeriesInkFacetQueryCount:
    """작품별 집계(user_collection_item_work_title_facets)가 요청당 정확히
    1회만 실행되고, 아이템 수가 늘어도 쿼리 수가 늘지 않는지(행별 쿼리 없음)
    고정한다 — 팔레트를 item_rows 순회 중 매번 다시 조회하는 회귀를 막는다."""

    def test_작품_집계_쿼리는_요청당_한_번만_실행된다(
        self, user_client, make_collection_item
    ):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        user, client = user_client()
        make_collection_item(user, name="A1", work_title="작품 A")
        make_collection_item(user, name="B1", work_title="작품 B")

        with CaptureQueriesContext(connection) as ctx:
            client.get("/collection/")

        facet_queries = [
            query
            for query in ctx.captured_queries
            if "GROUP BY" in query["sql"].upper() and "work_title" in query["sql"]
        ]
        assert len(facet_queries) == 1

    def test_아이템_수가_늘어도_요청당_총_쿼리_수는_늘지_않는다(
        self, make_user, user_client, make_collection_item
    ):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        small_user, small_client = user_client(username="query-count-small")
        for i in range(3):
            make_collection_item(small_user, name=f"소{i}", work_title=f"작품 소{i}")

        big_user, big_client = user_client(username="query-count-big")
        for i in range(15):
            make_collection_item(big_user, name=f"대{i}", work_title=f"작품 대{i}")

        with CaptureQueriesContext(connection) as small_ctx:
            small_client.get("/collection/")

        with CaptureQueriesContext(connection) as big_ctx:
            big_client.get("/collection/")

        assert len(big_ctx.captured_queries) == len(small_ctx.captured_queries)
