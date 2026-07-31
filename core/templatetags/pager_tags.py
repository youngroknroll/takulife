"""공용 페이지네이션 컴포넌트의 템플릿 태그.

``Paginator.get_elided_page_range``(및 그와 동등한 창 계산)는 현재 페이지
번호를 인자로 받아야 하는데 Django 템플릿은 인자를 받는 메서드를 호출할
수 없어서 존재한다. 계산 자체는 ``core.pagination``에 있어 템플릿 없이도
단위 테스트가 가능하다.
"""

from django import template

from core.pagination import pager_context

register = template.Library()


@register.simple_tag
def pager_data(page_obj):
    """``page_obj``의 페이저 뷰모델을 반환한다(core.pagination 참고)."""
    return pager_context(page_obj)
