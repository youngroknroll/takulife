"""쿼리스트링 pk 안전성 판별(core/query_params.py).

순수 문자열 판정, DB 불필요. archive.py의 ?subject=와 collection.py의
?visit_record= 가 공유하던 중복 검사를 뽑아낸 함수라, 경계값 각각이
조작된 쿼리 파라미터가 500 오류로 이어지는 걸 막는지 확인한다.
"""

import pytest

from core.query_params import is_safe_pk_string

pytestmark = pytest.mark.unit


class TestIsSafePkString:
    def test_정상_숫자_문자열이면_참이다(self):
        assert is_safe_pk_string("123") is True

    def test_비ASCII_숫자이면_거짓이다(self):
        # 위첨자 2 — isdigit()는 True를 돌려주지만 int()는 예외를 던진다.
        assert is_safe_pk_string("²") is False

    def test_18자를_넘으면_거짓이다(self):
        assert is_safe_pk_string("9" * 19) is False

    def test_18자면_참이다(self):
        assert is_safe_pk_string("9" * 18) is True

    def test_빈_문자열이면_거짓이다(self):
        assert is_safe_pk_string("") is False

    def test_숫자가_아니면_거짓이다(self):
        assert is_safe_pk_string("abc") is False
