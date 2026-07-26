"""Pager window computation for the shared pagination component.

Kept out of the template layer on purpose: the windowing rules below are
arithmetic with several boundary cases, and Django templates cannot call a
method with arguments (``Paginator.get_elided_page_range`` needs the current
page number), so a template-only version would have to be an unreadable chain
of ``{% if %}``s that no test could reach directly.

The window is a block-aligned range (``[1-5]``, ``[6-10]``, …) followed by a
trailing last page, not a window centred on the current page — see
``page_window`` for the exact rule.
"""

ELLIPSIS = "…"

# Numbered pages shown per block. Five keeps the row narrow enough to stay on
# one line at 320px while still giving a sense of position.
WINDOW = 5
# How far the «/» double arrows jump.
JUMP = 5


def _block_bounds(current: int, total: int) -> tuple:
    block_start = ((current - 1) // WINDOW) * WINDOW + 1
    block_end = min(block_start + WINDOW - 1, total)
    # Singleton last block (total ≡ 1 mod 5 → block is exactly [total]) is
    # merged into the previous block so the final page never shows a lone
    # number (user decision 2026-07-27). Pull its start back one window.
    if block_start == total and block_start > 1:
        block_start -= WINDOW
    return block_start, block_end


def page_window(current: int, total: int) -> list:
    """Return the page numbers to render, with ELLIPSIS where truncated.

    The window is the 5-page block ``current`` falls in — block-aligned, not
    centred, so paging with «/» always lands on a fresh block instead of a
    shifted one. The last page is always reachable: it is appended after the
    block (with an ELLIPSIS gap, or without one when it is directly adjacent
    to the block, since a gap of one page is not worth marking). There is
    never a leading ELLIPSIS — the block itself always starts the range. A
    singleton last block (``total`` a lone number on its own) is merged into
    the previous block instead, so the final page never renders alone.
    """
    if total <= WINDOW:
        return list(range(1, total + 1))

    block_start, block_end = _block_bounds(current, total)

    pages: list = list(range(block_start, block_end + 1))
    if block_end < total:
        if block_end + 1 != total:
            pages.append(ELLIPSIS)
        pages.append(total)
    return pages


def pager_context(page_obj) -> dict:
    """Build everything the pager template needs from a Django ``Page``.

    Arrows are gated by block position, not by clamped targets: ``show_back``
    is false only in the first block and ``show_forward`` only in the last,
    so both the single-step and 5-page-jump arrows on a side appear or vanish
    together — there is no longer a disabled-but-present state to render.
    """
    total = page_obj.paginator.num_pages
    current = page_obj.number
    block_start, block_end = _block_bounds(current, total)
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
        "show_back": block_start > 1,
        "show_forward": block_end < total,
    }
