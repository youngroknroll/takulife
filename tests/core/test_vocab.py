"""core.vocab 어휘 계약 — 도메인이 인정하는 카테고리·지역 slug가 실제로
그 목록에 있는지 지킨다."""
import pytest

from core.vocab import is_valid_category


pytestmark = pytest.mark.unit


def test_카테고리_어휘에_콘서트가_포함된다():
    assert is_valid_category("concert") is True
