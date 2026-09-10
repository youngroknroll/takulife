"""닉네임 정규화·검증 규칙(트랙 29). 폼·매니저·마이그레이션이 공유하는 순수 함수."""
import re
import unicodedata

from django.core.exceptions import ValidationError

MIN_LENGTH = 2
MAX_LENGTH = 20
NICKNAME_PATTERN = re.compile(r"^[0-9A-Za-z_가-힣]{2,20}$")
RESERVED_NICKNAMES = frozenset(
    {
        "admin",
        "administrator",
        "root",
        "system",
        "staff",
        "moderator",
        "mod",
        "support",
        "official",
        "superuser",
        "takulife",
        "관리자",
        "운영자",
        "스태프",
        "시스템",
        "공식",
        "고객센터",
        "운영팀",
        "타쿠라이프",
    }
)
# 백필 값(회원<pk>)과 사용자 선택 값이 영원히 겹치지 않도록 이 패턴은 예약한다.
RESERVED_NICKNAME_PATTERN = re.compile(r"^회원\d+$")
LENGTH_ERROR = "닉네임은 2자 이상 20자 이하로 입력해 주세요."


def normalize_nickname(raw: str) -> str:
    return unicodedata.normalize("NFKC", raw).strip()


def validate_nickname(value: str) -> None:
    if len(value) < MIN_LENGTH:
        raise ValidationError(LENGTH_ERROR, code="min_length")
    if len(value) > MAX_LENGTH:
        raise ValidationError(LENGTH_ERROR, code="max_length")
    if not NICKNAME_PATTERN.fullmatch(value):
        raise ValidationError(
            "닉네임은 한글, 영문, 숫자, _(밑줄)만 사용할 수 있습니다.", code="invalid"
        )
    if value.lower() in RESERVED_NICKNAMES or RESERVED_NICKNAME_PATTERN.fullmatch(
        value
    ):
        raise ValidationError("이 닉네임은 사용할 수 없습니다.", code="reserved")
