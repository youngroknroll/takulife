"""core/categories.py — 카테고리 팔레트 슬롯 색상표(트랙 27 2단계).

Category.palette_slot(0~PALETTE_SLOT_COUNT-1)이 실제로 어떤 색인지의
단일 출처. static/css/tokens.css의 --cat-slot-{n}-soft/-ink 값과
반드시 일치해야 한다 — 여기 값이 바뀌면 CSS도 같이 바꿔야 한다.

슬롯 0~6은 기존 CATEGORY 7종(core/vocab.py)이 쓰던 색과 정확히 같다.
시딩 마이그레이션이 기존 이벤트 색을 한 픽셀도 바꾸지 않으려면 이
순서를 core.vocab.CATEGORY 튜플 순서와 맞춰야 한다.
"""

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
