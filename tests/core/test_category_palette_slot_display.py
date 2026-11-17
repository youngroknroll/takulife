"""공개 화면 점 색 속성 태그(`palette_slot_attr`)의 동작을 검증한다(트랙 59).

⚠️ core/migrations/0006_seed_categories가 테스트 DB에도 적용된다.
새 슬러그는 core.vocab.CATEGORY 시딩분과 겹치지 않게 고른다.
"""

from django.template import Context, Template
import pytest

from core.context_processors import category_palette_slots
from core.models import Category
from core.vocab import CATEGORY_SOURCE_LABELS

pytestmark = [pytest.mark.django_db, pytest.mark.domain]


def _슬롯을_비운_카테고리를_만든다():
    category = Category.objects.create(slug="slotless_fair", label="슬롯없는 박람회")
    Category.objects.filter(pk=category.pk).update(palette_slot=None)
    return category.slug


def _행이_없는_슬러그를_고른다():
    assert not Category.objects.filter(slug="no_such_row").exists()
    return "no_such_row"


@pytest.mark.parametrize(
    "슬러그를_준비한다",
    [
        pytest.param(_슬롯을_비운_카테고리를_만든다, id="슬롯_미배정"),
        pytest.param(_행이_없는_슬러그를_고른다, id="카테고리_행_없음"),
    ],
)
def test_슬롯이_없거나_행이_없는_슬러그로_속성을_그리면_속성이_붙지_않는다(슬러그를_준비한다):
    슬러그 = 슬러그를_준비한다()
    템플릿 = Template("{% load category_dots %}<span{% palette_slot_attr slug %}></span>")

    출력 = 템플릿.render(Context({"slug": 슬러그}))

    assert 출력 == "<span></span>"


def test_슬롯이_배정된_새_카테고리_슬러그로_속성을_그리면_그_슬롯_번호_속성이_붙는다():
    category = Category.objects.create(slug="slotted_fair", label="슬롯있는 박람회")
    category.refresh_from_db()
    템플릿 = Template("{% load category_dots %}<span{% palette_slot_attr slug %}></span>")

    출력 = 템플릿.render(Context({"slug": category.slug}))

    assert 출력 == f'<span data-palette-slot="{category.palette_slot}"></span>'


@pytest.mark.parametrize(
    "슬러그",
    [pytest.param("", id="빈_문자열")]
    + [pytest.param(slug, id=label) for slug, label in CATEGORY_SOURCE_LABELS.items()],
)
def test_고정_카테고리나_빈_슬러그로_속성을_그리면_조회_없이_속성이_붙지_않는다(
    슬러그, django_assert_num_queries
):
    템플릿 = Template("{% load category_dots %}<span{% palette_slot_attr slug %}></span>")
    컨텍스트 = Context({"slug": 슬러그})

    with django_assert_num_queries(0):
        출력 = 템플릿.render(컨텍스트)

    assert 출력 == "<span></span>"


def test_프로세서가_준_슬롯_맵으로_include를_거쳐_여러_점을_그려도_조회는_한_번이다(
    django_assert_num_queries,
):
    카테고리들 = [
        Category.objects.create(slug="dots_fair_a", label="점박람회가"),
        Category.objects.create(slug="dots_fair_b", label="점박람회나"),
        Category.objects.create(slug="dots_fair_c", label="점박람회다"),
    ]
    안쪽 = Template("{% load category_dots %}<i{% palette_slot_attr slug %}></i>")
    바깥 = Template("{% for slug in slugs %}{% include inner %}{% endfor %}")
    슬러그들 = [category.slug for category in 카테고리들]

    with django_assert_num_queries(0):
        프로세서_값 = category_palette_slots(None)
    with django_assert_num_queries(1):
        출력 = 바깥.render(Context({**프로세서_값, "inner": 안쪽, "slugs": 슬러그들}))

    for category in 카테고리들:
        category.refresh_from_db()
        assert f'data-palette-slot="{category.palette_slot}"' in 출력


def test_비활성이고_게시_행사가_없는_카테고리의_속성을_그려도_슬롯이_반납되지_않고_속성에_실린다():
    category = Category.objects.create(slug="retired_fair", label="폐지된 박람회", is_active=False)
    category.refresh_from_db()
    렌더_전_슬롯 = category.palette_slot
    assert 렌더_전_슬롯 is not None
    템플릿 = Template("{% load category_dots %}<span{% palette_slot_attr slug %}></span>")

    출력 = 템플릿.render(Context({**category_palette_slots(None), "slug": category.slug}))

    category.refresh_from_db()
    assert 출력 == f'<span data-palette-slot="{렌더_전_슬롯}"></span>'
    assert category.palette_slot == 렌더_전_슬롯
