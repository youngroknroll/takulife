import re
from pathlib import Path

import pytest

from core.vocab import CATEGORY

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOKENS_CSS = PROJECT_ROOT / "static/css/tokens.css"


def _defined_custom_properties(css_text):
    return set(re.findall(r"--([a-zA-Z0-9_-]+):", css_text))


def test_tokens_css는_모든_카테고리_슬러그에_대해_soft_ink_토큰을_정의한다():
    """계약 가드: static/css/tokens.css는 core.vocab.CATEGORY의 모든 카테고리
    슬러그에 대해 --cat-{slug}-soft와 --cat-{slug}-ink를 정의해야 한다 —
    "슬러그 = CSS 이름" 원칙(G10)을 커스텀 프로퍼티 계층까지 확장한 것이다.

    templates/core/home.html의 포스터 없음 폴백은 전체 슬러그를 그대로
    보간한다: var(--cat-{{ row.category_slug }}-soft, --brand-soft). 슬러그를
    줄인 토큰 이름(예: popup_store에 --cat-popup-soft)은 절대 매칭되지
    않아, var()가 카테고리 색상 대신 조용히 --brand-soft로 폴백해버린다.
    """
    defined = _defined_custom_properties(TOKENS_CSS.read_text())

    missing = []
    for slug, _label in CATEGORY:
        for suffix in ("soft", "ink"):
            name = f"cat-{slug}-{suffix}"
            if name not in defined:
                missing.append(f"--{name}")

    assert not missing, f"tokens.css missing category tokens: {missing}"
