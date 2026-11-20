"""인증 도메인 픽스처.

valid_password와 make_verified_user는 tests/core/도 쓰게 되면서
루트 conftest.py로 올라갔다.
"""

from django.conf import Settings
import pytest


@pytest.fixture
def production_password_hashers():
    """운영 설정 모듈의 비밀번호 해셔 목록(테스트 설정은 MD5뿐이라 따로 읽는다)."""
    return Settings("config.settings").PASSWORD_HASHERS
