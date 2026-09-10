"""닉네임 검증 규칙(accounts.validators.validate_nickname) 단위 테스트."""
from django.core.exceptions import ValidationError

import pytest

from accounts.validators import normalize_nickname, validate_nickname

pytestmark = pytest.mark.unit


def test_길이가_2자_미만인_닉네임은_검증에서_거부된다():
    with pytest.raises(ValidationError):
        validate_nickname("a")


@pytest.mark.parametrize(
    "value",
    ["닉 네임", "ㄱㄴㄷ", "ａｂｃ", "ab​cd", "nick!"],
)
def test_허용되지_않는_문자가_포함된_닉네임은_검증에서_거부된다(value):
    with pytest.raises(ValidationError):
        validate_nickname(value)


@pytest.mark.parametrize(
    "value",
    [
        "admin",
        "Admin",
        "타쿠라이프",
        "운영자",
        "회원12",
        normalize_nickname("ａｄｍｉｎ"),
    ],
)
def test_예약어_및_회원숫자_패턴_닉네임은_검증에서_거부된다(value):
    with pytest.raises(ValidationError):
        validate_nickname(value)


def test_정규화는_NFKC_변환과_앞뒤_공백_제거를_적용한다():
    assert normalize_nickname("  ａｂｃ１２ ") == "abc12"
    assert normalize_nickname("닉네임") == "닉네임"
