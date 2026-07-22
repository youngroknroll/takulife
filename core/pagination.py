"""Pager window computation for the shared pagination component.

Kept out of the template layer on purpose: the windowing rules below are
arithmetic with several boundary cases, and Django templates cannot call a
method with arguments (``Paginator.get_elided_page_range`` needs the current
page number), so a template-only version would have to be an unreadable chain
of ``{% if %}``s that no test could reach directly.
"""

ELLIPSIS = "…"

# Numbered pages shown around the current one. Five keeps the row narrow enough
# to stay on one line at 320px while still giving a sense of position.
WINDOW = 5
# How far the «/» double arrows jump.
JUMP = 5
# Below this the whole range fits comfortably, so the ± JUMP arrows would only
# duplicate what the numbers already offer.
JUMP_ARROWS_MIN_PAGES = 10


def page_window(current: int, total: int) -> list:
    """Return the page numbers to render, with ELLIPSIS where truncated.

    The window is centred on ``current`` and then clamped so it never runs off
    either end — at the boundaries it slides inward instead of shrinking, so
    the control keeps a stable width as the user pages through.
    """
    if total <= WINDOW:
        return list(range(1, total + 1))

    half = WINDOW // 2
    start = min(max(current - half, 1), total - WINDOW + 1)
    end = start + WINDOW - 1

    pages: list = []
    if start > 1:
        pages.append(ELLIPSIS)
    pages.extend(range(start, end + 1))
    if end < total:
        pages.append(ELLIPSIS)
    return pages


def pager_context(page_obj) -> dict:
    """Build everything the pager template needs from a Django ``Page``.

    Arrow targets are clamped rather than hidden at the ends: the template
    renders a disabled cell so the control does not change width — a row that
    reflows as you reach the last page makes the next click land somewhere
    unexpected.
    """
    total = page_obj.paginator.num_pages
    current = page_obj.number
    return {
        "pages": page_window(current, total),
        # Exposed so the template can tell a gap apart from a page number
        # without hardcoding the glyph in two places.
        "ellipsis": ELLIPSIS,
        "current": current,
        "total": total,
        "previous": max(current - 1, 1),
        "next": min(current + 1, total),
        "jump_back": max(current - JUMP, 1),
        "jump_forward": min(current + JUMP, total),
        "has_previous": current > 1,
        "has_next": current < total,
        # The ± JUMP arrows only earn their space once paging one at a time is
        # genuinely tedious.
        "show_jump_arrows": total > JUMP_ARROWS_MIN_PAGES,
    }
