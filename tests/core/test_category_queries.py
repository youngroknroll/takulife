"""카테고리 어휘 조회가 모듈 상수 대신 DB(Category)를 보게 되는지 검증한다
(트랙 27 5단계 Phase A). core/vocab.py의 `is_valid_category`는 시그니처를
그대로 유지하되 내부에서 core.models.Category를 조회해야 하고,
새 라벨 조회 함수 `core.categories.category_label(slug)`가 그 짝이다.

⚠️ core/migrations/0006_seed_categories가 테스트 DB에도 적용된다
(tests/core/test_category_model.py 모듈 독스트링 참고). 이 파일의
새 슬러그는 core.vocab.CATEGORY 시딩분과 겹치지 않게 고른다.
"""
import pytest

from core.models import Category
from core.vocab import CATEGORY, is_valid_category

pytestmark = [pytest.mark.django_db, pytest.mark.domain]


def test_런타임에_추가한_카테고리가_같은_프로세스에서_바로_유효해진다():
    새_슬러그 = "vintage_market"
    assert 새_슬러그 not in dict(CATEGORY)

    Category.objects.create(slug=새_슬러그, label="빈티지 마켓")

    assert is_valid_category(새_슬러그) is True


def test_비활성_카테고리도_어휘_검증은_통과한다():
    # 확정 결정: 비활성 ≠ 삭제. 기존 이벤트가 이 슬러그로 재게시될 때
    # events/services.py:69의 is_valid_category가 활성 여부를 이유로
    # 거부하면 안 된다(비활성화 이후에도 슬러그·라벨은 그대로 남는다는
    # Category 모델 계약, tests/core/test_category_model.py 참고).
    비활성_슬러그 = "retired_market"
    category = Category.objects.create(slug=비활성_슬러그, label="폐지된 마켓")
    category.is_active = False
    category.save()

    assert is_valid_category(비활성_슬러그) is True


def test_빈_문자열_카테고리는_계속_미분류로_유효하다():
    assert is_valid_category("") is True


def test_어휘에_없는_임의_문자열은_계속_거부된다():
    assert is_valid_category("카페/팝업") is False


def test_카테고리_라벨_조회는_DB를_본다():
    from core.categories import category_label

    새_슬러그 = "night_market"
    Category.objects.create(slug=새_슬러그, label="나이트 마켓")

    assert category_label(새_슬러그) == "나이트 마켓"


def test_알_수_없는_슬러그의_라벨_조회는_슬러그를_그대로_돌려준다():
    from core.categories import category_label

    assert category_label("존재하지_않는_슬러그") == "존재하지_않는_슬러그"
