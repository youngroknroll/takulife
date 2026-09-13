"""HomeConfig 강조 카테고리와 홈 화면 렌더링을 검증한다.

다루는 범위:
- HomeConfig.get_solo: 싱글턴 동작(pk=1, 멱등)
- HomeConfig.featured_category_pairs: 폴백(활성 카테고리 전체, DB 기준), 필터링, 순서
- home view: category_tiles 하위 호환과 설정 반영 렌더링

⚠️ core/migrations/0006_seed_categories가 테스트 DB에도 적용되어(트랙 27 3단계),
TestFeaturedCategoryPairs의 모든 테스트는 core.vocab.CATEGORY와 같은 슬러그를
가진 Category 행이 이미 DB에 존재하는 상태에서 시작한다. 새로 만드는 슬러그는
이 시딩된 슬러그와 겹치지 않게 고른다(tests/core/test_category_model.py 모듈 독스트링과 동일한 전제).
"""
import pytest
from django.test import Client

from core.models import Category, HomeConfig
from core.vocab import CATEGORY


@pytest.mark.django_db
class TestHomeConfigSingleton:
    pytestmark = pytest.mark.domain

    def test_HomeConfig를_처음_조회하면_pk_1인_싱글턴_행이_반환된다(self):
        config = HomeConfig.get_solo()

        assert config.pk == 1

    def test_HomeConfig를_반복_조회해도_같은_pk의_싱글턴_행이_반환된다(self):
        first = HomeConfig.get_solo()
        second = HomeConfig.get_solo()

        assert first.pk == second.pk


@pytest.mark.django_db
class TestFeaturedCategoryPairs:
    pytestmark = pytest.mark.domain

    def test_강조_카테고리가_비어있으면_활성_카테고리만_sort_order_순서로_반환한다(self):
        """I-01: 대체값이 core.vocab이 아니라 DB의 활성 Category를
        sort_order 순으로 읽는지 검증한다. 비활성화한 concert는 빠지고,
        시딩 이후 새로 만든 활성 카테고리는 sort_order 순서상 제자리에
        끼어 들어와야 한다."""
        Category.objects.create(
            slug="zz_new_active", label="새로운활성카테고리", sort_order=3
        )
        concert = Category.objects.get(slug="concert")
        concert.is_active = False
        concert.save()

        config = HomeConfig.get_solo()
        config.featured_categories = []
        config.save()

        pairs = config.featured_category_pairs()

        assert pairs == [
            ("popup_store", "팝업스토어"),
            ("collaboration_cafe", "콜라보 카페"),
            ("theater_bonus", "극장 특전"),
            ("goods_reservation", "굿즈 예약"),
            ("zz_new_active", "새로운활성카테고리"),
            ("exhibition", "전시"),
            ("fan_meeting", "팬미팅"),
        ]

    def test_강조_카테고리가_비어있을_때_런타임에_추가한_카테고리가_같은_프로세스에서_바로_반영된다(self):
        """I-03: 이 테스트가 증명하려는 것 — featured_category_pairs가
        core.vocab.CATEGORY(모듈 임포트 시점에 고정된 상수)가 아니라 DB를
        실시간으로 조회한다는 것. core.vocab.CATEGORY에는 없는 슬러그를
        테스트 중에 새로 만들어 결과에 나타나야만 어휘 상수가 아니라 DB를
        봤다는 증거가 된다 — 매번 쿼리하는 구현이면 자명하게 통과하니,
        어휘에 없는 슬러그로 검증해 그 우연한 통과를 배제한다."""
        assert "zz_runtime_only" not in dict(CATEGORY)
        Category.objects.create(
            slug="zz_runtime_only", label="런타임전용카테고리", sort_order=999
        )

        config = HomeConfig.get_solo()
        config.featured_categories = []
        config.save()

        pairs = config.featured_category_pairs()

        assert ("zz_runtime_only", "런타임전용카테고리") in pairs

    def test_강조_카테고리를_지정하면_저장된_순서대로_해당_카테고리만_반환한다(self):
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        pairs = config.featured_category_pairs()

        assert pairs == [("exhibition", "전시"), ("popup_store", "팝업스토어")]

    def test_강조_카테고리에_존재하지_않는_슬러그가_있으면_걸러내고_나머지만_반환한다(self):
        config = HomeConfig.get_solo()
        config.featured_categories = ["bogus", "exhibition"]
        config.save()

        pairs = config.featured_category_pairs()

        slugs = [s for s, _ in pairs]
        assert "bogus" not in slugs
        assert "exhibition" in slugs
        assert len(slugs) == 1

    def test_강조_카테고리로_지정된_슬러그가_비활성이면_홈_타일_후보에서_제외된다(self):
        """I-04(판단 필요): 이 트랙의 확정 사용자 결정("비활성이어도 게시
        이벤트가 있으면 소비자 필터에 남는다")은 이벤트 목록 필터 화면을
        겨냥한 결정이다. featured_category_pairs는 필터가 아니라 스태프가
        직접 고른 홈 큐레이션 타일이라, 여기서는 활성 카테고리만 노출한다는
        반대 판단을 적용했다 — 반대로 결정될 수 있으니 오케스트레이터
        확인이 필요하다."""
        exhibition = Category.objects.get(slug="exhibition")
        exhibition.is_active = False
        exhibition.save()

        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        pairs = config.featured_category_pairs()

        assert pairs == [("popup_store", "팝업스토어")]


@pytest.mark.django_db
class TestHomeViewCategoryTilesIntegration:
    pytestmark = pytest.mark.web

    def test_HomeConfig_행이_없으면_홈_화면에_전체_카테고리_타일이_어휘_순서대로_노출된다(self):
        """하위 호환: HomeConfig 행이 없으면 어휘 전체 카테고리가 노출된다."""
        resp = Client().get("/")

        assert resp.status_code == 200
        slugs = [t["slug"] for t in resp.context["category_tiles"]]
        assert slugs == [s for s, _ in CATEGORY]
        assert len(slugs) == len(CATEGORY)

    def test_HomeConfig_행이_없고_행사가_없으면_모든_카테고리_타일의_건수가_0이다(self):
        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        for slug, _ in CATEGORY:
            assert tiles[slug]["count"] == 0

    def test_HomeConfig에_강조_카테고리를_설정하면_홈_화면에_선택한_카테고리_타일만_순서대로_노출된다(self):
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        resp = Client().get("/")

        slugs = [t["slug"] for t in resp.context["category_tiles"]]
        assert slugs == ["exhibition", "popup_store"]

    def test_강조_카테고리_설정_시_각_타일에_해당_카테고리_행사_건수가_정확히_반영된다(self, make_event):
        make_event(category="exhibition")
        config = HomeConfig.get_solo()
        config.featured_categories = ["exhibition", "popup_store"]
        config.save()

        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["exhibition"]["count"] == 1
        assert tiles["popup_store"]["count"] == 0

    def test_카테고리_타일은_slug_label_count_필드를_항상_포함한다(self):
        """category_tiles는 템플릿과의 계약이라 slug/label/count를 항상 포함해야 한다."""
        resp = Client().get("/")

        for tile in resp.context["category_tiles"]:
            assert "slug" in tile
            assert "label" in tile
            assert "count" in tile
