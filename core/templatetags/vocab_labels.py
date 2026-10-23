"""저장된 어휘 값을 요청 언어로 보여 주는 템플릿 필터.

저장값은 항상 한국어 원문이므로, 화면에는 이 필터를 거쳐 요청 언어로 번역해 보인다.
어휘 밖의 사용자 입력은 그대로 나온다.
"""
from django import template

from core.vocab import collection_item_type_label, personal_category_label

register = template.Library()

register.filter("personal_category_label", personal_category_label)
register.filter("collection_item_type_label", collection_item_type_label)
