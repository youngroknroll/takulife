"""커맨드바 검색어 길이 상한 — staff/search.py의 search_term 경계 처리."""

from django.test import RequestFactory
import pytest

from staff.search import MAX_SEARCH_LENGTH, search_term

pytestmark = pytest.mark.unit


def test_검색어가_상한_길이를_넘으면_잘려서_반환된다():
    request = RequestFactory().get("/", {"q": "a" * 150})

    result = search_term(request)

    assert len(result) == MAX_SEARCH_LENGTH
    assert result == ("a" * 150)[:MAX_SEARCH_LENGTH]
