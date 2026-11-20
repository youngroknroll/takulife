"""비밀번호 해셔 설정."""

from django.contrib.auth.hashers import Argon2PasswordHasher


class CalibratedArgon2PasswordHasher(Argon2PasswordHasher):
    """운영에서 새 비밀번호 저장에 쓰는 Argon2id 해셔."""
