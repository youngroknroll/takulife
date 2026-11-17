"""카테고리 라벨 요소에 한글 원문 언어 속성을 붙이는 템플릿 태그."""

from django import template
from django.utils.html import format_html

from core.categories import category_label_lang

register = template.Library()


@register.simple_tag
def category_lang_attr(label):
    """라벨 요소에 붙일 `lang` 속성 문자열을 반환한다. 붙일 필요가 없으면 빈 문자열."""
    lang = category_label_lang(label)
    if not lang:
        return ""
    return format_html(' lang="{}"', lang)
