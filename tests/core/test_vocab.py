"""core.vocab 어휘 계약 — 도메인이 인정하는 카테고리·지역 slug가 실제로
그 목록에 있는지 지킨다.

is_valid_category가 트랙 27 5단계에서 DB(Category)를 보게 되어, 이 시나리오는
마이그레이션이 심어 둔 기존 슬러그("concert")가 실제로 유효 판정되는지 보는
것이라 unit이 아니라 domain(DB 필요)이다. tests/core/test_category_queries.py는
이 파일에서 새로 만든 슬러그만 다루므로 중복이 아니다."""
import pytest

from core.vocab import is_valid_category


pytestmark = [pytest.mark.django_db, pytest.mark.domain]


def test_카테고리_어휘에_콘서트가_포함된다():
    assert is_valid_category("concert") is True
