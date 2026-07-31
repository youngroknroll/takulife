"""공용 페이지네이션 컴포넌트의 페이저 창 계산.

일부러 템플릿 레이어에 두지 않았다: 아래 창 계산 규칙은 경계 조건이
여럿인 산술이고, Django 템플릿은 인자를 받는 메서드를 호출할 수 없어서
(``Paginator.get_elided_page_range``는 현재 페이지 번호가 필요하다)
템플릿만으로 구현하면 테스트가 직접 닿을 수 없는 읽기 힘든
``{% if %}`` 연쇄가 됐을 것이다.

창은 현재 페이지를 중심으로 한 창이 아니라 블록 단위로 정렬된 범위
(``[1-5]``, ``[6-10]``, …) 뒤에 마지막 페이지가 붙는 형태다 — 정확한
규칙은 ``page_window`` 참고.
"""

ELLIPSIS = "…"

# 블록당 보여줄 페이지 번호 수. 5개면 320px에서도 한 줄에 들어가면서
# 현재 위치를 파악할 수 있다.
WINDOW = 5
# «/» 두 겹 화살표가 한 번에 건너뛰는 페이지 수.
JUMP = 5


def _block_bounds(current: int, total: int) -> tuple:
    block_start = ((current - 1) // WINDOW) * WINDOW + 1
    block_end = min(block_start + WINDOW - 1, total)
    # 마지막 블록이 페이지 하나뿐이면(total ≡ 1 mod 5 → 블록이 [total]
    # 하나) 마지막 페이지가 외따로 보이지 않도록 이전 블록에 합친다.
    # 시작점을 한 창만큼 앞으로 당긴다.
    if block_start == total and block_start > 1:
        block_start -= WINDOW
    return block_start, block_end


def page_window(current: int, total: int) -> list:
    """렌더링할 페이지 번호 목록을 반환한다. 생략된 부분은 ELLIPSIS로 표시.

    창은 ``current``가 속한 5페이지 블록이다 — 중심 정렬이 아니라 블록
    정렬이라 «/»로 넘겨도 매번 어긋난 창이 아니라 새 블록에 정확히
    도달한다. 마지막 페이지는 항상 접근 가능하도록 블록 뒤에 붙인다
    (블록과 바로 이웃하면 한 페이지 차이는 표시할 가치가 없어 ELLIPSIS
    없이, 아니면 ELLIPSIS와 함께). 앞쪽에는 ELLIPSIS가 절대 붙지 않는다
    — 블록 자체가 항상 범위의 시작이다. 마지막 블록이 페이지 하나뿐이면
    (``total``이 외따로 있으면) 이전 블록에 합쳐서 마지막 페이지가 혼자
    렌더링되지 않게 한다.
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
    """Django ``Page``로부터 페이저 템플릿에 필요한 모든 값을 만든다.

    화살표는 클램프된 목표값이 아니라 블록 위치로 켜고 끈다:
    ``show_back``은 첫 블록에서만, ``show_forward``는 마지막 블록에서만
    false라 한쪽의 한 칸 이동 화살표와 5페이지 점프 화살표가 항상 함께
    나타나거나 사라진다 — 비활성화됐지만 화면엔 남아 있는 상태를 그릴
    필요가 없다.
    """
    total = page_obj.paginator.num_pages
    current = page_obj.number
    block_start, block_end = _block_bounds(current, total)
    return {
        "pages": page_window(current, total),
        # 템플릿이 생략 기호를 두 곳에 하드코딩하지 않고도 페이지 번호와
        # 빈 구간을 구분할 수 있도록 노출한다.
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
