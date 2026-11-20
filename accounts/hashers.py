"""비밀번호 해셔 설정."""

from django.contrib.auth.hashers import Argon2PasswordHasher


class CalibratedArgon2PasswordHasher(Argon2PasswordHasher):
    """운영에서 새 비밀번호 저장에 쓰는 Argon2id 해셔."""

    # 메모리는 OWASP 최소 권장치를 유지하고, 반복 횟수만 올려 로그인 시간을
    # 기존 PBKDF2와 비슷하게 맞췄다. 측정 근거는 docs/BE/password-hashing.md.
    time_cost = 24
    memory_cost = 19456
    parallelism = 1
