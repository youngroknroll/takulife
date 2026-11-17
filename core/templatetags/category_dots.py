"""공개 화면 카테고리 점의 색 슬롯 속성을 그리는 템플릿 태그."""

from django import template
from django.utils.html import format_html

from core.categories import palette_slot_by_slug
from core.vocab import CATEGORY_SOURCE_LABELS

register = template.Library()


@register.simple_tag(takes_context=True)
def palette_slot_attr(context, slug):
    """슬러그의 팔레트 슬롯 속성 문자열을 반환한다.

    고정 카테고리는 슬러그 색 규칙이 칠하므로 조회하지 않는다.
    """
    if not slug or slug in CATEGORY_SOURCE_LABELS:
        return ""
    # 요청 없이 템플릿만 그리는 경우(프로세서 값이 없다)에도 속성이 빠지지 않게 직접 조회한다.
    slots = context.get("category_palette_slots")
    if slots is None:
        slots = palette_slot_by_slug()
    slot = slots.get(slug)
    if slot is None:
        return ""
    return format_html(' data-palette-slot="{}"', slot)
