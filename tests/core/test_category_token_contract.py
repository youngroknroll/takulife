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
    """Contract guard: static/css/tokens.css must define --cat-{slug}-soft and
    --cat-{slug}-ink for every category slug in core.vocab.CATEGORY — the G10
    "slug = CSS name" principle extended to the custom-property layer.

    templates/core/home.html's poster-less fallback interpolates the full
    vocab slug directly: var(--cat-{{ row.category_slug }}-soft, --brand-soft).
    A token name that abbreviates the slug (e.g. --cat-popup-soft for
    popup_store) never matches, so the var() falls back silently to
    --brand-soft instead of the category's color.
    """
    defined = _defined_custom_properties(TOKENS_CSS.read_text())

    missing = []
    for slug, _label in CATEGORY:
        for suffix in ("soft", "ink"):
            name = f"cat-{slug}-{suffix}"
            if name not in defined:
                missing.append(f"--{name}")

    assert not missing, f"tokens.css missing category tokens: {missing}"
