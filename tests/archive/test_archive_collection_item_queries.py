"""아카이브 읽기 계층(archive/queries.py) 단위 테스트 — 컬렉션 아이템(CollectionItem) 조회.

list_user_collection_items(필터 포함)/user_collection_item_filter_values/
user_collection_item_summary_counts/user_collection_item_work_title_facets를
검증한다.
"""

import pytest

from archive.models import CollectionItem
from archive.queries import (
    list_user_collection_items,
    user_collection_item_filter_values,
    user_collection_item_summary_counts,
    user_collection_item_work_title_facets,
)

pytestmark = pytest.mark.domain


# ---------------------------------------------------------------------------
# list_user_collection_items (PR-C1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_컬렉션_아이템_목록_조회는_소유자로_범위를_좁힌다(make_user):
    user = make_user(username="ci-query-owner")
    other = make_user(username="ci-query-other")
    mine = CollectionItem.objects.create(user=user, name="내 굿즈")
    CollectionItem.objects.create(user=other, name="남의 굿즈")

    items = list(list_user_collection_items(user))

    assert items == [mine]


# ---------------------------------------------------------------------------
# list_user_collection_items 필터 (PR-C5, CP16~22). `duplicate`/`tradeable`은
# quantity/tradeable_quantity에서 파생된 값이다 — CollectionItem에는 별도의
# duplicate_count나 tradeable 플래그 필드가 없다(§3-1).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_작품명_필터는_완전_일치하는_항목만_반환한다(make_user):
    user = make_user(username="ci-query-work-title")
    match = CollectionItem.objects.create(user=user, name="일치", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="불일치", work_title="작품 B")

    items = list(list_user_collection_items(user, work_title="작품 A"))

    assert items == [match]


@pytest.mark.django_db
def test_중복_필터는_별도_필드_없이_수량_2개_이상_여부로_판정된다(make_user):
    """`duplicate=True`는 quantity >= 2인 행을 선택한다 — 별도의 duplicate_count
    필드는 없다(§3-1)."""
    user = make_user(username="ci-query-duplicate")
    two = CollectionItem.objects.create(user=user, name="둘", quantity=2)
    one = CollectionItem.objects.create(user=user, name="하나", quantity=1)

    assert list(list_user_collection_items(user, duplicate=True)) == [two]
    assert list(list_user_collection_items(user, duplicate=False)) == [one]
    assert not hasattr(two, "duplicate_count")


@pytest.mark.django_db
def test_교환가능_필터는_별도_필드_없이_교환가능_수량_1개_이상_여부로_판정된다(
    make_user,
):
    """`tradeable=True`는 tradeable_quantity > 0인 행을 선택한다 — 별도의
    플래그 필드는 없다(§3-1)."""
    user = make_user(username="ci-query-tradeable")
    tradeable = CollectionItem.objects.create(
        user=user, name="교환 가능", quantity=3, tradeable_quantity=1
    )
    not_tradeable = CollectionItem.objects.create(
        user=user, name="교환 불가", quantity=3, tradeable_quantity=0
    )

    assert list(list_user_collection_items(user, tradeable=True)) == [tradeable]
    assert list(list_user_collection_items(user, tradeable=False)) == [not_tradeable]


@pytest.mark.django_db
def test_보유_필터는_별도_필드_없이_수량_1개_이상_여부로_판정된다(make_user):
    """`owned=True`는 quantity > 0인 행을 선택한다 — duplicate/tradeable과
    같은 파생 필터 패턴으로, 별도의 owned 플래그 필드는 없다(§3-1)."""
    user = make_user(username="ci-query-owned")
    held = CollectionItem.objects.create(user=user, name="가진 것", quantity=3)
    not_held = CollectionItem.objects.create(user=user, name="안 가진 것", quantity=0)

    assert list(list_user_collection_items(user, owned=True)) == [held]
    assert list(list_user_collection_items(user, owned=False)) == [not_held]


@pytest.mark.django_db
def test_구함_필터_False는_구함이_아닌_항목만_반환한다(make_user):
    """`is_wanted=False`는 quantity와 무관하게 is_wanted가 False인 행을 선택한다
    — "보유"와는 다르다(보유/구함은 독립된 축, 계획서 §D1). quantity>0이면서
    is_wanted=True인 행은 "보유"이기도 하지만 is_wanted=False 결과에서는
    제외돼야 한다. 이는 예전에 웹 /collection/?is_wanted=false로 접근하던
    동작(지금은 레거시 북마크 호환을 위해 ?owned=true로 리다이렉트)의 쿼리
    계층 가드다 — API 호출자는 /api/collection-items/에서 여전히
    is_wanted=false를 그대로 쓴다."""
    user = make_user(username="ci-query-is-wanted-false")
    not_wanted = CollectionItem.objects.create(user=user, name="보유", quantity=3, is_wanted=False)
    owned_and_wanted = CollectionItem.objects.create(
        user=user, name="보유하며구함", quantity=2, is_wanted=True
    )

    assert list(list_user_collection_items(user, is_wanted=False)) == [not_wanted]
    assert owned_and_wanted not in list(list_user_collection_items(user, is_wanted=False))


@pytest.mark.django_db
def test_통합검색어는_이름_작품명_캐릭터명_메모에서_일치하되_상품유형은_대상에서_제외한다(
    make_user,
):
    """`q`는 name/work_title/character_name/memo를 icontains로 좁힌다 —
    list_user_personal_entries의 q 패턴과 동일. item_type은 의도적으로 검색
    대상이 아니며, item_type에만 일치하는 미끼 행은 제외돼야 한다."""
    user = make_user(username="ci-query-q")
    other = make_user(username="ci-query-q-other")
    by_name = CollectionItem.objects.create(user=user, name="레어 스탬프")
    by_work_title = CollectionItem.objects.create(
        user=user, name="굿즈 1", work_title="레어 작품"
    )
    by_character_name = CollectionItem.objects.create(
        user=user, name="굿즈 2", character_name="레어 캐릭터"
    )
    by_memo = CollectionItem.objects.create(user=user, name="굿즈 3", memo="레어 메모")
    item_type_decoy = CollectionItem.objects.create(
        user=user, name="굿즈 4", item_type="레어 타입"
    )
    other_user_same_name = CollectionItem.objects.create(user=other, name="레어 스탬프")

    items = set(list_user_collection_items(user, q="레어"))

    assert items == {by_name, by_work_title, by_character_name, by_memo}
    assert item_type_decoy not in items
    assert other_user_same_name not in items


@pytest.mark.django_db
def test_빈_통합검색어는_아무_항목도_걸러내지_않는다(make_user):
    """빈 `q`는 아무것도 걸러내면 안 된다.

    `if q:`는 정확성 가드가 아니라 쿼리 최적화다: Django는
    `Q(field__icontains="")`를 `field LIKE '%%'`로 렌더링해 필드값과 무관하게
    모든 행에 매치되므로, `if q is not None:`으로 바꿔도 동작은 동일하고 이
    테스트도 여전히 통과해야 한다 — 이 가드는 빈 문자열의 과잉 필터링을 막는
    게 아니라 no-op인 icontains 절 4개를 건너뛰기 위한 것이다.

    검색 대상 네 필드 모두를 빈 기본값이 아닌 서로 다른 값으로 채운 이유는,
    진짜로 깨진 조회(예: 가드를 없앤 채 `icontains`를 `exact`로 바꾼 경우)가
    필드가 우연히 비어 있는 행에서만 우연히 일치해 통과해버리는 일을 막기
    위해서다.
    """
    user = make_user(username="ci-query-q-empty")
    first = CollectionItem.objects.create(
        user=user,
        name="굿즈 1",
        work_title="작품 1",
        character_name="캐릭터 1",
        memo="메모 1",
    )
    second = CollectionItem.objects.create(
        user=user,
        name="굿즈 2",
        work_title="작품 2",
        character_name="캐릭터 2",
        memo="메모 2",
    )

    items = set(list_user_collection_items(user, q=""))

    assert items == {first, second}


# ---------------------------------------------------------------------------
# user_collection_item_filter_values (PR-C5b-1). user_visit_category_values는
# 호출자가 core.vocab 라벨을 해석한 뒤 중복 제거하지만(archive/queries.py는
# core.vocab을 임포트하지 않는다), work_title/character_name/item_type은
# vocab 해석 단계가 없는 자유 텍스트라서 중복 제거와 공백 제외를 뷰가 아니라
# 이 쿼리 계층에서 직접 처리한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_필터_선택지_조회는_소유자로_범위를_좁히고_중복값을_제거한다(make_user):
    user = make_user(username="ci-filter-values-user")
    other = make_user(username="ci-filter-values-other")
    CollectionItem.objects.create(user=user, name="굿즈 1", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="굿즈 2", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="굿즈 3", character_name="캐릭터 A")
    CollectionItem.objects.create(user=user, name="굿즈 4", character_name="캐릭터 A")
    CollectionItem.objects.create(user=user, name="굿즈 5", item_type="스탬프")
    CollectionItem.objects.create(user=user, name="굿즈 6", item_type="스탬프")
    CollectionItem.objects.create(
        user=other, name="남의 굿즈", work_title="작품 A", character_name="캐릭터 A", item_type="스탬프"
    )

    values = user_collection_item_filter_values(user)

    assert values == {
        "work_title": ["작품 A"],
        "character_name": ["캐릭터 A"],
        "item_type": ["스탬프"],
    }


@pytest.mark.django_db
def test_필터_선택지_목록은_정렬된_순서로_반환된다(make_user):
    """각 목록은 정렬돼 있어야 한다 — C5b-2가 이 값을 그대로 <select> 옵션으로
    렌더한다.

    이 테스트는 계약을 문서화할 뿐 회귀를 막지는 못한다. 마이그레이션 0019의
    (user, work_title) 복합 인덱스 덕분에 이 테이블 크기에서는 `.order_by()`를
    지워도 Postgres 플래너가 이미 정렬된 행을 돌려줘 테스트가 실패하지 않는다
    (실제로 지우고 재실행해 확인함). `.order_by()`가 필요한 근거는 ORDER BY
    없는 DISTINCT의 순서가 일반적으로 미정의라는 데 있다(예: 행 수나 통계가
    바뀌면 플래너가 다른 HashAggregate 계획을 고를 수 있음) — 플래너를
    인덱스 기반 계획에서 강제로 벗어나게 해(`SET enable_indexscan/enable_sort
    = off` 등) 실제로 정렬되지 않은 출력을 확인해 검증했다. 이 강제 플래너
    확인은 이 저장소가 아니라 Postgres 플래너를 테스트하는 셈이라 자동
    테스트로는 반복하지 않는다.
    """
    user = make_user(username="ci-filter-values-order")
    CollectionItem.objects.create(user=user, name="굿즈 1", work_title="작품 C")
    CollectionItem.objects.create(user=user, name="굿즈 2", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="굿즈 3", work_title="작품 B")

    values = user_collection_item_filter_values(user)

    assert values["work_title"] == ["작품 A", "작품 B", "작품 C"]


@pytest.mark.django_db
def test_값이_비어있는_필드는_필터_선택지_목록에_포함되지_않는다(make_user):
    user = make_user(username="ci-filter-values-blank")
    CollectionItem.objects.create(
        user=user,
        name="굿즈 1",
        work_title="작품 B",
        character_name="캐릭터 B",
        item_type="피규어",
    )
    CollectionItem.objects.create(user=user, name="굿즈 2")

    values = user_collection_item_filter_values(user)

    assert values == {
        "work_title": ["작품 B"],
        "character_name": ["캐릭터 B"],
        "item_type": ["피규어"],
    }


@pytest.mark.django_db
def test_컬렉션_아이템이_없는_사용자의_필터_선택지는_모두_빈_목록이다(make_user):
    user = make_user(username="ci-filter-values-empty")

    values = user_collection_item_filter_values(user)

    assert values == {"work_title": [], "character_name": [], "item_type": []}


# ---------------------------------------------------------------------------
# user_collection_item_summary_counts (PR-C5b-1, 컬렉션 3축 독립화 트랙에서
# 개정, 2026-07-28). owned/wanted/tradeable은 분할이 아니라 서로 독립된
# 세 축이다(계획서 §D1, .docs/plans/2026-07-15-collection-domain-design-plan.md:55,
# "wanted와 보유 공존 허용") — 한 행이 owned이면서 동시에 wanted일 수 있어
# owned_count + wanted_count가 전체 개수가 아니다. total_count가 따로
# 존재하는 이유다. 웹의 구함 칩은 여전히 ?is_wanted=true를 쓰지만, 옛 보유
# 칩 URL(?is_wanted=false)은 이제 ?owned=true로 302 리다이렉트된다(레거시
# 북마크 호환). DRF API는 ?is_wanted=false를 원래 의미 그대로 유지한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_보유_구함_집계는_수량_합계가_아니라_행_개수를_센다(make_user):
    user = make_user(username="ci-summary-counts-user")
    other = make_user(username="ci-summary-counts-other")
    CollectionItem.objects.create(user=user, name="보유 굿즈", quantity=5, is_wanted=False)
    CollectionItem.objects.create(user=user, name="구함 굿즈 1", quantity=0, is_wanted=True)
    CollectionItem.objects.create(user=user, name="구함 굿즈 2", quantity=0, is_wanted=True)
    CollectionItem.objects.create(user=other, name="남의 굿즈", quantity=9, is_wanted=False)

    counts = user_collection_item_summary_counts(user)

    assert counts == {
        "owned_count": 1,
        "wanted_count": 2,
        "tradeable_count": 0,
        "total_count": 3,
    }


@pytest.mark.django_db
def test_컬렉션_아이템이_없는_사용자의_보유_구함_집계는_0이다(make_user):
    user = make_user(username="ci-summary-counts-empty")

    counts = user_collection_item_summary_counts(user)

    assert counts == {
        "owned_count": 0,
        "wanted_count": 0,
        "tradeable_count": 0,
        "total_count": 0,
    }


@pytest.mark.django_db
def test_보유_구함_교환희망_세_축은_서로_독립적으로_집계된다(make_user):
    """owned/wanted/tradeable은 상호 배타적 분할이 아니라 서로 독립된 세 축이다
    (계획서 §D1, .docs/plans/2026-07-15-collection-domain-design-plan.md:55,
    "wanted와 보유 공존 허용" — quantity>0, is_wanted=True, tradeable_quantity>0이
    한 행에서 임의로 조합될 수 있다). 한 행이 여러 축에 동시에 집계될 수 있다."""
    user = make_user(username="ci-summary-counts-axes")
    CollectionItem.objects.create(
        user=user, name="품목1", quantity=3, is_wanted=False, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="품목2", quantity=0, is_wanted=True, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="품목3", quantity=2, is_wanted=True, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="품목4", quantity=4, is_wanted=False, tradeable_quantity=2
    )
    CollectionItem.objects.create(
        user=user, name="품목5", quantity=3, is_wanted=True, tradeable_quantity=2
    )

    counts = user_collection_item_summary_counts(user)

    assert counts["owned_count"] == 4
    assert counts["wanted_count"] == 3
    assert counts["tradeable_count"] == 2


@pytest.mark.django_db
def test_전체_집계는_보유_구함_카운트의_단순_합과_다르다(make_user):
    """total_count는 축 소속과 무관하게 사용자가 가진 모든 행(존재 자체)을
    센다. owned_count + wanted_count로 유도할 수 없다 — 계획서 §D1
    (.docs/plans/2026-07-15-collection-domain-design-plan.md:55, "wanted와
    보유 공존 허용")에 따라 한 행이 여러 축에 중복 집계될 수 있으므로, 축별
    카운트로는 전체 재고 총량을 대신할 수 없다."""
    user = make_user(username="ci-summary-counts-total")
    other = make_user(username="ci-summary-counts-total-other")
    CollectionItem.objects.create(
        user=user, name="줄1", quantity=3, is_wanted=False, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="줄2", quantity=0, is_wanted=True, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="줄3", quantity=0, is_wanted=False, tradeable_quantity=0
    )
    CollectionItem.objects.create(user=other, name="타인의 줄", quantity=1, is_wanted=False)

    counts = user_collection_item_summary_counts(user)

    assert counts["total_count"] == 3
    assert counts["owned_count"] + counts["wanted_count"] == 2
    assert counts["owned_count"] + counts["wanted_count"] != counts["total_count"]


# ---------------------------------------------------------------------------
# user_collection_item_summary_counts — tradeable_count (컬렉션 리디자인
# 백엔드). tradeable_count는 owned/wanted 옆의 세 번째 분할이 아니라 겹치는
# 파생 축이다 — tradeable_quantity>0인 보유 아이템은 owned_count와
# tradeable_count 양쪽에 동시에 집계돼야 한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_요약_집계는_교환가능_수량이_1개_이상인_항목_개수를_tradeable_count로_반환한다(make_user):
    user = make_user(username="ci-summary-tradeable")
    CollectionItem.objects.create(
        user=user, name="교환 가능 1", quantity=2, tradeable_quantity=1
    )
    CollectionItem.objects.create(
        user=user, name="교환 가능 2", quantity=3, tradeable_quantity=2
    )
    CollectionItem.objects.create(
        user=user, name="교환 불가", quantity=3, tradeable_quantity=0
    )

    counts = user_collection_item_summary_counts(user)

    assert counts["tradeable_count"] == 2


@pytest.mark.django_db
def test_교환가능_집계는_보유_구함_분할과_겹치는_축이라_보유_항목이_교환가능이면_양쪽_모두_집계된다(make_user):
    """tradeable_count는 상호 배타 분할이 아니다 — is_wanted=False인 보유
    아이템도 tradeable_quantity>0이면 owned_count와 tradeable_count 양쪽에
    동시에 집계된다(owned/wanted처럼 배타적으로 나뉘지 않고 의도적으로
    겹친다)."""
    user = make_user(username="ci-summary-tradeable-overlap")
    CollectionItem.objects.create(
        user=user,
        name="보유하며_교환가능",
        is_wanted=False,
        quantity=2,
        tradeable_quantity=1,
    )

    counts = user_collection_item_summary_counts(user)

    assert counts["owned_count"] == 1
    assert counts["tradeable_count"] == 1


# ---------------------------------------------------------------------------
# user_collection_item_work_title_facets (컬렉션 리디자인 백엔드,
# 작품별 색상 인덱스/필터 근거 집계). work_title이 비어있는 행은 제외하고,
# count 내림차순·동수는 work_title 오름차순으로 정렬하며 소유자로 범위를
# 좁힌다.
# 각 facet 은 {"work_title", "count", "first_id"} dict 이며 first_id 는
# 그 작품의 최초 등록(가장 작은 id) 아이템의 id 다 — 순번 기반 색 배정의
# 근거가 되는 필드라 해시 대체(색 배정을 순번으로 바꾸는 이번 변경)의 핵심.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_작품명별_항목_facet_집계는_작품명이_비어있는_항목을_제외한다(make_user):
    user = make_user(username="ci-work-title-counts-blank")
    item = CollectionItem.objects.create(user=user, name="굿즈 1", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="굿즈 2")

    facets = user_collection_item_work_title_facets(user)

    assert facets == [{"work_title": "작품 A", "count": 1, "first_id": item.id}]


@pytest.mark.django_db
def test_작품명별_항목_facet_집계는_개수_내림차순_동수는_작품명_오름차순으로_정렬된다(make_user):
    user = make_user(username="ci-work-title-counts-order")
    # 작품 C: 1건, 작품 A: 2건, 작품 B: 2건 (A/B는 개수가 같아 동수 정렬 케이스)
    c1 = CollectionItem.objects.create(user=user, name="C1", work_title="작품 C")
    a1 = CollectionItem.objects.create(user=user, name="A1", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="A2", work_title="작품 A")
    b1 = CollectionItem.objects.create(user=user, name="B1", work_title="작품 B")
    CollectionItem.objects.create(user=user, name="B2", work_title="작품 B")

    facets = user_collection_item_work_title_facets(user)

    assert facets == [
        {"work_title": "작품 A", "count": 2, "first_id": a1.id},
        {"work_title": "작품 B", "count": 2, "first_id": b1.id},
        {"work_title": "작품 C", "count": 1, "first_id": c1.id},
    ]


@pytest.mark.django_db
def test_작품명별_항목_facet_집계는_소유자로_범위를_좁힌다(make_user):
    user = make_user(username="ci-work-title-counts-owner")
    other = make_user(username="ci-work-title-counts-other")
    item = CollectionItem.objects.create(user=user, name="내 굿즈", work_title="작품 A")
    CollectionItem.objects.create(user=other, name="남의 굿즈", work_title="작품 A")

    facets = user_collection_item_work_title_facets(user)

    assert facets == [{"work_title": "작품 A", "count": 1, "first_id": item.id}]


@pytest.mark.django_db
def test_작품명별_항목_facet_집계의_first_id는_그_작품의_최초_등록_아이템_id다(make_user):
    user = make_user(username="ci-work-title-counts-first-id")
    first = CollectionItem.objects.create(user=user, name="첫번째", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="두번째", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="세번째", work_title="작품 A")

    facets = user_collection_item_work_title_facets(user)

    assert facets == [{"work_title": "작품 A", "count": 3, "first_id": first.id}]
