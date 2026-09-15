import re
from pathlib import Path

import pytest

from core.categories import PALETTE
from core.models import Category

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOKENS_CSS = PROJECT_ROOT / "static/css/tokens.css"


def _defined_custom_properties(css_text):
    return set(re.findall(r"--([a-zA-Z0-9_-]+):", css_text))


def test_tokens_css는_팔레트_풀의_모든_슬롯에_대해_soft_ink_토큰을_정의한다():
    """계약 가드: static/css/tokens.css는 core.categories.PALETTE의 모든
    슬롯 번호(0~PALETTE_SLOT_COUNT-1)에 대해 --cat-slot-{n}-soft와
    --cat-slot-{n}-ink를 정의해야 한다.

    스태프가 만드는 카테고리는 고정 슬러그가 없어 "슬러그 = CSS 이름"
    원칙(G10)이 성립하지 않는다. 대신 카테고리는 팔레트 슬롯 번호를
    참조하고, 이 토큰이 실제 색을 낸다. 기존 슬러그 기반 --cat-{slug}-*
    토큰은 소비 화면이 아직 슬러그로 직접 참조하므로 남아 있다(공존,
    소비처 전환은 이후 단계). 소비처가 슬롯 참조로 전환되면
    templates/core/home.html처럼 폴백 없이 var()를 보간하는 지점에서
    슬롯 토큰이 하나라도 비면 스와치 배경이 조용히 사라진다.
    """
    defined = _defined_custom_properties(TOKENS_CSS.read_text())

    missing = []
    for slot in range(len(PALETTE)):
        for suffix in ("soft", "ink"):
            name = f"cat-slot-{slot}-{suffix}"
            if name not in defined:
                missing.append(f"--{name}")

    assert not missing, f"tokens.css missing palette slot tokens: {missing}"


def _all_property_values(css_text, property_name):
    return re.findall(rf"--{re.escape(property_name)}:\s*([^;]+);", css_text)


def test_tokens_css의_팔레트_슬롯_hex_값은_PALETTE와_전부_일치한다():
    """계약 가드: tokens.css의 --cat-slot-{n}-soft/-ink 값이
    core.categories.PALETTE의 hex와 실제로 같아야 한다. 위 존재 가드는
    이름만 확인하고 값은 확인하지 않아, 두 파일이 조용히 어긋날 수 있다
    (스태프 화면은 PALETTE에서 hex를 계산해 인라인 style로 찍고, 소비자
    화면은 CSS 토큰을 쓰므로 어긋나면 두 화면 색이 달라진다).

    블록 위치(:root vs :root[data-theme="dark"])에 기대지 않고, "슬롯
    이름마다 값이 정확히 2번 정의되고 그 두 값의 집합이 {light, dark}
    값의 집합과 같다"로 판정해 CSS 구조 변경에 덜 취약하게 했다. 대소문자·
    앞뒤 공백은 정규화해서 비교한다.

    [실측] 현재 48개 토큰 값은 PALETTE와 전부 일치해 이 테스트는 Green으로
    태어난다. 뮤테이션 지점: core/categories.py의 PALETTE 슬롯 아무 hex나
    한 글자 바꾸면 Red가 된다.
    """
    css_text = TOKENS_CSS.read_text()

    mismatches = []
    for slot, colors in enumerate(PALETTE):
        for suffix, keys in (
            ("soft", ("light_soft", "dark_soft")),
            ("ink", ("light_ink", "dark_ink")),
        ):
            name = f"cat-slot-{slot}-{suffix}"
            values = [v.strip().lower() for v in _all_property_values(css_text, name)]
            expected = {colors[key].strip().lower() for key in keys}
            if len(values) != 2 or set(values) != expected:
                mismatches.append((name, values, sorted(expected)))

    assert not mismatches, mismatches


@pytest.mark.django_db
def test_활성_카테고리는_모두_유효한_팔레트_슬롯에_배정돼_있다():
    """계약 가드: 활성 카테고리(is_active=True)는 palette_slot이 None이
    아니어야 하고, 그 값은 0~PALETTE_SLOT_COUNT-1 범위 안이어야 한다.

    이 값이 CSS 토큰 인덱스로 그대로 쓰이므로, 범위를 벗어나거나 비어
    있으면 위 토큰 존재 가드를 통과해도 실제 렌더에서 색이 사라진다.
    """
    invalid = []
    for category in Category.objects.filter(is_active=True):
        slot = category.palette_slot
        if slot is None or not (0 <= slot < len(PALETTE)):
            invalid.append((category.slug, slot))

    assert not invalid, f"슬롯 배정이 잘못된 활성 카테고리: {invalid}"
