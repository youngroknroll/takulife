from pathlib import Path
import re

import pytest

from core.categories import PALETTE
from core.models import Category
from core.vocab import CATEGORY_SOURCE_LABELS

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
    참조하고, 이 토큰이 실제 색을 낸다. 슬러그 기반 --cat-{slug}-* 토큰은
    트랙 58에서 삭제됐고, 고정 카테고리 점은 --dot-{slug} 색을 쓴다. 슬롯
    잉크 토큰은 공개 화면이 새 카테고리 점 색으로 읽는다(트랙 59). 토큰이
    하나라도 비면 점 색이 조용히 사라지므로 이 계약은 유지한다.
    """
    defined = _defined_custom_properties(TOKENS_CSS.read_text())

    missing = []
    for slot in range(len(PALETTE)):
        for suffix in ("soft", "ink"):
            name = f"cat-slot-{slot}-{suffix}"
            if name not in defined:
                missing.append(f"--{name}")

    assert not missing, f"tokens.css missing palette slot tokens: {missing}"


def test_tokens_css의_점_색_토큰_이름은_고정_카테고리_슬러그_집합과_같다():
    """계약 가드: tokens.css의 --dot-{slug} 토큰 이름 집합은 고정 카테고리
    슬러그 집합(core.vocab.CATEGORY_SOURCE_LABELS)과 같아야 한다. 값(hex)은
    보지 않는다. 한쪽만 늘거나 줄면 점 색이 비거나 쓰이지 않는 토큰이 남는다.
    """
    defined = _defined_custom_properties(TOKENS_CSS.read_text())

    css_slugs = {name.removeprefix("dot-") for name in defined if name.startswith("dot-")}
    vocab_slugs = set(CATEGORY_SOURCE_LABELS)

    assert css_slugs == vocab_slugs, (
        f"CSS에만 있음: {sorted(css_slugs - vocab_slugs)}, "
        f"어휘에만 있음: {sorted(vocab_slugs - css_slugs)}"
    )


def _all_property_values(css_text, property_name):
    return re.findall(rf"--{re.escape(property_name)}:\s*([^;]+);", css_text)


def test_tokens_css의_팔레트_슬롯_hex_값은_PALETTE와_전부_일치한다():
    """계약 가드: tokens.css의 --cat-slot-{n}-soft/-ink 값이
    core.categories.PALETTE의 hex와 실제로 같아야 한다. 위 존재 가드는
    이름만 확인하고 값은 확인하지 않아, 두 파일이 조용히 어긋날 수 있다
    (스태프 화면은 PALETTE에서 hex를 계산해 인라인 style로 찍고, 소비자
    화면은 CSS 토큰을 쓰므로 어긋나면 두 화면 색이 달라진다).

    슬롯 이름마다 값이 정확히 1번 정의되고 그 값이 PALETTE의 라이트
    값과 같아야 한다(다크 모드가 없어 같은 속성의 두 번째 정의는
    결함이다). 대소문자·앞뒤 공백은 정규화해서 비교한다.

    [계산] 12슬롯 × soft/ink = 24개 토큰 값이 대상이다. 뮤테이션 지점:
    core/categories.py의 PALETTE 슬롯 hex 한 글자를 바꾸거나, tokens.css에
    같은 슬롯 속성을 한 번 더 정의하면 Red가 된다.
    """
    css_text = TOKENS_CSS.read_text()

    mismatches = []
    for slot, colors in enumerate(PALETTE):
        for suffix, key in (
            ("soft", "light_soft"),
            ("ink", "light_ink"),
        ):
            name = f"cat-slot-{slot}-{suffix}"
            values = [v.strip().lower() for v in _all_property_values(css_text, name)]
            expected = colors[key].strip().lower()
            if len(values) != 1 or values[0] != expected:
                mismatches.append((name, values, expected))

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
