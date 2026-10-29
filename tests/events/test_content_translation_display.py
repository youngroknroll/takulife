"""events.content_translation.select_display에 대한 단위 테스트 — 해시
일치·언어 격리·해시 불일치·빈 저장소·미지원 언어에서의 노출 선택을 다룬다.
"""

import pytest

from events.content_translation import DisplayText, select_display, source_hash

pytestmark = pytest.mark.unit


def _source(**overrides):
    base = {
        "title": "2026 도쿄 코믹마켓",
        "work_title": "원피스",
        "location_name": "도쿄 빅사이트",
        "summary": "10월 24일 개최",
    }
    return {**base, **overrides}


def _en():
    return {
        "title": "2026 Tokyo Comic Market",
        "work_title": "One Piece",
        "location_name": "Tokyo Big Sight",
        "summary": "Held on October 24",
    }


def _zh():
    return {
        "title": "2026 东京漫展",
        "work_title": "海贼王",
        "location_name": "东京国际展览中心",
        "summary": "10月24日举办",
    }


def _text_translations(source):
    return {
        "source_hash": source_hash(source),
        "manual": False,
        "en": _en(),
        "ja": None,
        "zh-hans": _zh(),
    }


def test_해시가_일치하고_번역이_있으면_번역을_반환한다():
    source = _source()
    text_translations = _text_translations(source)

    result = select_display(source, text_translations, "en")

    assert result == DisplayText(fields=_en(), is_translated=True)


def test_해당_언어가_격리돼_None이면_원문을_반환한다():
    source = _source()
    text_translations = _text_translations(source)

    result = select_display(source, text_translations, "ja")

    assert result == DisplayText(fields=source, is_translated=False)


def test_해시가_불일치하면_원문을_반환한다():
    source = _source()
    text_translations = _text_translations(source)
    changed_source = _source(title="2026 변경된 제목")

    result = select_display(changed_source, text_translations, "en")

    assert result == DisplayText(fields=changed_source, is_translated=False)


def test_번역_저장소가_빈_dict이면_원문을_반환한다():
    source = _source()

    result = select_display(source, {}, "en")

    assert result == DisplayText(fields=source, is_translated=False)


def test_언어가_ko이면_원문을_반환한다():
    source = _source()
    text_translations = _text_translations(source)

    result = select_display(source, text_translations, "ko")

    assert result == DisplayText(fields=source, is_translated=False)


def test_모르는_언어_코드이면_원문을_반환한다():
    source = _source()
    text_translations = _text_translations(source)

    result = select_display(source, text_translations, "fr")

    assert result == DisplayText(fields=source, is_translated=False)


def test_원문_반환_시_번역_대상_네_필드만_담긴다():
    source_with_extra = {**_source(), "view_count": 10}

    result = select_display(source_with_extra, {}, "en")

    assert result.fields == _source()
    assert set(result.fields.keys()) == {"title", "work_title", "location_name", "summary"}


@pytest.mark.parametrize(
    "broken_en",
    [
        {"title": "x"},
        {**_en(), "title": 123},
        {**_en(), "summary": None},
    ],
    ids=["필드_누락", "값이_정수", "값이_None"],
)
def test_해당_언어_엔트리의_네_필드가_전부_문자열이_아니면_원문을_반환한다(broken_en):
    source = _source()
    text_translations = {**_text_translations(source), "en": broken_en}

    result = select_display(source, text_translations, "en")

    assert result == DisplayText(fields=source, is_translated=False)
