"""운영 비밀번호 해셔 설정을 적용했을 때 새 비밀번호가 Argon2id로
저장되는지 지킨다.
"""

from django.contrib.auth.hashers import make_password
from django.test import override_settings
import pytest

from accounts.hashers import CalibratedArgon2PasswordHasher

pytestmark = pytest.mark.unit


def test_운영_해셔_목록에서_새_비밀번호는_argon2id_접두로_저장된다(production_password_hashers):
    # Given: 운영 설정의 비밀번호 해셔 목록을 적용한다.
    with override_settings(PASSWORD_HASHERS=production_password_hashers):
        # When: 해셔를 지정하지 않고 비밀번호를 해시한다.
        해시값 = make_password("임시비밀번호123!")

        # Then: 첫 해셔(Argon2id)로 저장된다.
        assert 해시값.startswith("argon2$argon2id$")


def test_accounts_hashers의_argon2_해셔는_지정한_time_cost_memory_cost_parallelism으로_인코딩한다():
    # Given: 운영 해셔 인스턴스를 직접 만든다.
    해셔 = CalibratedArgon2PasswordHasher()

    # When: 평문 비밀번호를 인코딩한다.
    인코딩 = 해셔.encode("임시비밀번호123!", 해셔.salt())

    # Then: 운영에서 정한 메모리·반복·병렬 값으로 저장된다.
    디코딩 = 해셔.decode(인코딩)
    assert (디코딩["memory_cost"], 디코딩["time_cost"], 디코딩["parallelism"]) == (19456, 24, 1)
