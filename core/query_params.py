"""요청 쿼리스트링에서 받은 값을 안전하게 pk로 쓸 수 있는지 판단한다."""


def is_safe_pk_string(ident: str) -> bool:
    """`ident`가 그대로 `int()`와 ORM pk 조회에 넘겨도 안전한 숫자 문자열이면 True.

    18자리 상한은 PostgreSQL `bigint` 최댓값(19자리)보다 한 자리 짧게 잡아,
    자릿수 비교만으로 DB 정수 범위 초과를 걸러낸다.
    """
    return ident.isascii() and ident.isdigit() and len(ident) <= 18
