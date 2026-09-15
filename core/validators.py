"""카테고리 슬러그 형식 검증(트랙 27). accounts/validators.py의
validate_nickname과 같은 전제 — 필드 validators로 등록해 매니저를
거치지 않는 직접 생성 경로에서도 호출자가 full_clean()을 부르면 잡힌다."""
import re

from django.core.exceptions import ValidationError

CATEGORY_SLUG_PATTERN = re.compile(r"^[a-z0-9_]+$")


def validate_category_slug(value: str) -> None:
    if not CATEGORY_SLUG_PATTERN.fullmatch(value):
        raise ValidationError(
            "슬러그는 영문 소문자, 숫자, _(밑줄)만 사용할 수 있습니다.", code="invalid"
        )
