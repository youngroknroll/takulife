"""운영 비밀번호 해셔 설정을 적용했을 때 새 비밀번호가 Argon2id로
저장되는지 지킨다.
"""

from django.contrib.auth.hashers import make_password
from django.test import override_settings
import pytest

pytestmark = pytest.mark.unit


def test_운영_해셔_목록에서_새_비밀번호는_argon2id_접두로_저장된다(production_password_hashers):
    # Given: 운영 설정의 비밀번호 해셔 목록을 적용한다.
    with override_settings(PASSWORD_HASHERS=production_password_hashers):
        # When: 해셔를 지정하지 않고 비밀번호를 해시한다.
        해시값 = make_password("임시비밀번호123!")

        # Then: 첫 해셔(Argon2id)로 저장된다.
        assert 해시값.startswith("argon2$argon2id$")
