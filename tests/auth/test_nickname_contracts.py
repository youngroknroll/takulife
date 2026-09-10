"""닉네임 필수 입력 계약(트랙 29 NICK-10). createsuperuser가 nickname을
물어보도록 REQUIRED_FIELDS에 포함돼야 한다."""
from accounts.models import User

import pytest

pytestmark = pytest.mark.contract


def test_REQUIRED_FIELDS는_닉네임을_포함한다():
    assert "nickname" in User.REQUIRED_FIELDS


def test_닉네임_필드는_NULL을_허용하지_않는다():
    assert User._meta.get_field("nickname").null is False
