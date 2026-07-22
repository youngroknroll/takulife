"""Template tag for the shared pagination component.

Exists because ``Paginator.get_elided_page_range`` (and any equivalent
windowing) needs the current page number as an argument, and Django templates
cannot call a method with arguments. The arithmetic itself lives in
``core.pagination`` so it is unit-testable without a template.
"""

from django import template

from core.pagination import pager_context

register = template.Library()


@register.simple_tag
def pager_data(page_obj):
    """Return the pager view-model for ``page_obj`` (see core.pagination)."""
    return pager_context(page_obj)
