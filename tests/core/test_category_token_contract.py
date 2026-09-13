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
