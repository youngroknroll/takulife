"""events.content_translation.source_hash에 대한 단위 테스트.

번역 대상 네 필드(title·work_title·location_name·summary)만 해시에 반영되고,
다른 필드 변경·정규화 형태 차이에는 반응하지 않아야 한다는 계약을 다룬다.
"""
import unicodedata

import pytest

from events.content_translation import source_hash

pytestmark = pytest.mark.unit


def _fields(**overrides):
    base = {
        "title": "2026 도쿄 코믹마켓",
        "work_title": "원피스",
        "location_name": "도쿄 빅사이트",
        "summary": "10월 24일 개최",
    }
    return {**base, **overrides}


def test_같은_네_필드면_해시가_같다():
    first = source_hash(_fields())
    second = source_hash(_fields())

    assert first == second
    assert len(first) == 64
    assert all(ch in "0123456789abcdef" for ch in first)


def test_해시는_번역_대상_네_필드_외의_변경에는_반응하지_않는다():
    first = source_hash({**_fields(), "view_count": 1, "verified_at": "2026-10-24"})
    second = source_hash({**_fields(), "view_count": 999, "verified_at": None})

    assert first == second


@pytest.mark.parametrize(
    "field_name",
    ["title", "work_title", "location_name", "summary"],
)
def test_한_필드만_바뀌면_해시가_달라진다(field_name):
    first = source_hash(_fields())
    second = source_hash(_fields(**{field_name: "다른 값"}))

    assert first != second


def test_필드_경계가_이동하면_해시가_바뀐다():
    first = source_hash(_fields(title="AB", work_title="C"))
    second = source_hash(_fields(title="A", work_title="BC"))

    assert first != second


def test_같은_글자는_정규화_형태가_달라도_같은_해시다():
    nfc_title = unicodedata.normalize("NFC", "도쿄")
    nfd_title = unicodedata.normalize("NFD", "도쿄")

    first = source_hash(_fields(title=nfc_title))
    second = source_hash(_fields(title=nfd_title))

    assert first == second


def test_none_값은_빈_문자열과_같은_해시가_된다():
    first = source_hash(_fields(work_title=None))
    second = source_hash(_fields(work_title=""))

    assert first == second
