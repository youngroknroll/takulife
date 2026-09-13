"""core/categories.py — 카테고리 팔레트 슬롯 색상표(트랙 27 2단계).

Category.palette_slot(0~PALETTE_SLOT_COUNT-1)이 실제로 어떤 색인지의
단일 출처. static/css/tokens.css의 --cat-slot-{n}-soft/-ink 값과
반드시 일치해야 한다 — 여기 값이 바뀌면 CSS도 같이 바꿔야 한다.

슬롯 0~6은 기존 CATEGORY 7종(core/vocab.py)이 쓰던 색과 정확히 같다.
시딩 마이그레이션이 기존 이벤트 색을 한 픽셀도 바꾸지 않으려면 이
순서를 core.vocab.CATEGORY 튜플 순서와 맞춰야 한다.
"""

def category_exists(slug: str) -> bool:
    """슬러그가 Category 행으로 존재하면 True(비활성 포함).

    비활성 포함: 확정 결정 "비활성 ≠ 삭제" — 비활성화된 카테고리로 이미
    저장된 이벤트가 재게시될 때 어휘 검증(core.vocab.is_valid_category)에서
    거부되면 안 된다.
    """
    from core.models import Category

    return Category.objects.filter(slug=slug).exists()


def category_label(slug: str) -> str:
    """슬러그 → 라벨. 없으면 슬러그를 그대로 돌려준다(core.vocab.archive_status_label
    선례) — 카테고리 행이 지워져도 그 슬러그를 쓰던 기존 이벤트 렌더가 깨지지 않게 한다."""
    from core.models import Category

    label = Category.objects.filter(slug=slug).values_list("label", flat=True).first()
    return label if label is not None else slug


def reconcile_palette_slot(*, category_slug: str, published_count: int) -> None:
    """카테고리 팔레트 슬롯 반납·재획득을 판단·수행한다(트랙 27 6단계).

    규칙: 활성이거나 게시 이벤트가 1건 이상이면 슬롯을 유지/재획득하고,
    비활성이면서 게시 이벤트가 0건이면 슬롯을 반납한다. "활성이면 게시
    0건이어도 유지"가 핵심이다 — 그래야 방금 만든 카테고리가 생성 직후
    자기 슬롯을 스스로 반납하는 결함(BIR Critical)이 재발하지 않는다.

    호출 시점은 게시상태 전이·카테고리 활성 상태 전이뿐이다(호출부가
    보장). 조회(GET) 경로에서는 절대 호출하면 안 된다.
    """
    from django.db import IntegrityError

    from core.models import Category, PaletteSlotsExhaustedError

    try:
        category = Category.objects.get(slug=category_slug)
    except Category.DoesNotExist:
        return

    should_have_slot = category.is_active or published_count > 0

    if should_have_slot and category.palette_slot is None:
        try:
            category.palette_slot = Category._next_available_slot()
            category.save(update_fields=["palette_slot"])
        except (PaletteSlotsExhaustedError, IntegrityError):
            # 빈 슬롯이 없거나(고갈) 동시 요청과 경합해 실패했다 — 재획득
            # 실패는 palette_slot=None 폴백일 뿐, 호출부의 게시를 막지 않는다.
            pass
    elif not should_have_slot and category.palette_slot is not None:
        category.palette_slot = None
        category.save(update_fields=["palette_slot"])


def category_slugs() -> list[str]:
    """활성 카테고리 슬러그 목록(호출 시점 조회). LLM 추출 스키마·재검증이
    비활성 카테고리를 새로 제안하지 않도록 활성만 포함한다."""
    from core.models import Category

    return list(Category.objects.filter(is_active=True).values_list("slug", flat=True))


def active_category_choices() -> list[tuple[str, str]]:
    """활성 카테고리의 (slug, label) 쌍. 스태프가 새 이벤트를 등록할 때
    비활성 카테고리를 고르지 못하게, 등록 폼 선택지에만 쓴다."""
    from core.models import Category

    return list(Category.objects.filter(is_active=True).values_list("slug", "label"))


PALETTE: tuple[dict[str, str], ...] = (
    # 슬롯 0~6: 기존 CATEGORY 7종과 동일한 색(core/vocab.py 순서 그대로).
    {"light_soft": "#f3e8ff", "light_ink": "#7e22ce", "dark_soft": "#342442", "dark_ink": "#b17edc"},  # popup_store
    {"light_soft": "#f5ecdf", "light_ink": "#92633a", "dark_soft": "#3d3024", "dark_ink": "#bf9f82"},  # collaboration_cafe
    {"light_soft": "#e0e7ff", "light_ink": "#3730a3", "dark_soft": "#272541", "dark_ink": "#8f8bcf"},  # theater_bonus
    {"light_soft": "#d8f3ee", "light_ink": "#0f766e", "dark_soft": "#20413f", "dark_ink": "#64d8cf"},  # goods_reservation
    {"light_soft": "#e2e8f0", "light_ink": "#475569", "dark_soft": "#23354e", "dark_ink": "#839ec3"},  # exhibition
    {"light_soft": "#fce7f3", "light_ink": "#9d174d", "dark_soft": "#412530", "dark_ink": "#da769e"},  # fan_meeting
    {"light_soft": "#fef3c7", "light_ink": "#b45309", "dark_soft": "#422006", "dark_ink": "#fb923c"},  # concert
    # 슬롯 7~11: 신규 5개. 기존 7종과 겹치지 않는 색상군(red/yellow/lime/
    # green/sky)에서 골랐고, 각 조합은 라이트·다크 모두 WCAG AA 본문 기준
    # (4.5:1) 이상이다 — 정확한 대비비는 이 모듈을 다루는 계획/보고 문서에 기록.
    {"light_soft": "#fee2e2", "light_ink": "#b91c1c", "dark_soft": "#7f1d1d", "dark_ink": "#fca5a5"},  # red
    {"light_soft": "#fef9c3", "light_ink": "#854d0e", "dark_soft": "#713f12", "dark_ink": "#fde047"},  # yellow
    {"light_soft": "#ecfccb", "light_ink": "#3f6212", "dark_soft": "#365314", "dark_ink": "#bef264"},  # lime
    {"light_soft": "#dcfce7", "light_ink": "#166534", "dark_soft": "#14532d", "dark_ink": "#86efac"},  # green
    {"light_soft": "#e0f2fe", "light_ink": "#0369a1", "dark_soft": "#0c4a6e", "dark_ink": "#7dd3fc"},  # sky
)
