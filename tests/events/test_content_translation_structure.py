"""events.content_translation의 번역 제출 검증(validate_translations)에 대한
단위 테스트 — 구조 검사·전체 거부·언어별 격리 조합·NFC 정규화·필드 순서를 다룬다.
"""
import pytest

from events.content_translation import (
    TARGET_LANGUAGES,
    SubmissionRejected,
    quarantine_reason,
    validate_translations,
)

pytestmark = pytest.mark.unit


def _source():
    return {
        "title": "2026 도쿄 코믹마켓",
        "work_title": "원피스",
        "location_name": "도쿄 빅사이트",
        "summary": "10월 24일 개최",
    }


def _en():
    return {
        "title": "2026 Tokyo Comic Market",
        "work_title": "One Piece",
        "location_name": "Tokyo Big Sight",
        "summary": "Held on October 24",
    }


def _ja():
    return {
        "title": "2026 東京コミックマーケット",
        "work_title": "ワンピース",
        "location_name": "東京ビッグサイト",
        "summary": "10月24日開催",
    }


def _zh():
    return {
        "title": "2026 东京漫展",
        "work_title": "海贼王",
        "location_name": "东京国际展览中心",
        "summary": "10月24日举办",
    }


def _translations():
    return {"en": _en(), "ja": _ja(), "zh-hans": _zh()}


@pytest.mark.parametrize("language", TARGET_LANGUAGES)
def test_정상_번역은_세_언어_모두_격리되지_않는다(language):
    assert quarantine_reason(language, _source(), _translations()[language]) is None


def test_언어_하나만_제출하면_전체_거부된다():
    with pytest.raises(SubmissionRejected) as exc_info:
        validate_translations(_source(), {"en": _en()})

    assert exc_info.value.code == "schema"


_schema_violation_cases = [
    ("언어_안_필드_누락", lambda: {**_translations(), "ja": {k: v for k, v in _ja().items() if k != "summary"}}),
    ("필드_값이_비문자열", lambda: {**_translations(), "en": {**_en(), "title": 123}}),
    ("정의되지_않은_여분_언어", lambda: {**_translations(), "fr": _en()}),
    ("언어_안_여분_필드", lambda: {**_translations(), "en": {**_en(), "extra": "x"}}),
    ("translations가_리스트", lambda: [_en(), _ja(), _zh()]),
    ("언어_값이_None", lambda: {**_translations(), "en": None}),
]


@pytest.mark.parametrize(
    "build_translations", [case[1] for case in _schema_violation_cases], ids=[case[0] for case in _schema_violation_cases]
)
def test_키_집합이나_타입이_어긋나면_전체_거부된다(build_translations):
    with pytest.raises(SubmissionRejected) as exc_info:
        validate_translations(_source(), build_translations())

    assert exc_info.value.code == "schema"


def test_NUL_문자가_있으면_전체_거부된다():
    translations = {**_translations(), "en": {**_en(), "title": "2026 Tokyo\x00 Comic Market"}}

    with pytest.raises(SubmissionRejected) as exc_info:
        validate_translations(_source(), translations)

    assert exc_info.value.code == "nul"


def test_정상_제출은_격리_없이_세_언어를_모두_담는다():
    result = validate_translations(_source(), _translations())

    assert result.quarantined == {}
    assert isinstance(result.languages["en"], dict)
    assert isinstance(result.languages["ja"], dict)
    assert isinstance(result.languages["zh-hans"], dict)


def test_격리된_언어만_None이고_나머지는_그대로_담긴다():
    translations = {**_translations(), "ja": {**_ja(), "title": "2026 도쿄 コミックマーケット"}}

    result = validate_translations(_source(), translations)

    assert result.quarantined == {"ja": "hangul_residue"}
    assert result.languages["ja"] is None
    assert isinstance(result.languages["en"], dict)
    assert isinstance(result.languages["zh-hans"], dict)


def test_세_언어_모두_격리돼도_예외가_아니다():
    translations = {
        "en": {**_en(), "title": "2026 도쿄 Comic Market"},
        "ja": {**_ja(), "title": "2026 도쿄 コミックマーケット"},
        "zh-hans": {**_zh(), "title": "2026 도쿄 东京漫展"},
    }

    result = validate_translations(_source(), translations)

    assert set(result.quarantined.keys()) == {"en", "ja", "zh-hans"}
    assert result.languages == {"en": None, "ja": None, "zh-hans": None}


def test_저장되는_번역은_NFC로_정규화된다():
    # "Café"의 e를 분해형(e + 결합 악센트)으로 제출해도 저장은 NFC 합성형이어야 한다.
    # 2026을 그대로 두는 것은 숫자 검사(순서상 한글 잔존·문자 판정보다 먼저)가
    # 먼저 걸리지 않게 하기 위해서다.
    nfd_title = "2026 Cafe\u0301 Fair"
    translations = {**_translations(), "en": {**_en(), "title": nfd_title}}

    result = validate_translations(_source(), translations)

    assert result.languages["en"]["title"] == "2026 Café Fair"


def test_필드_순서에서_먼저_걸린_사유가_보고된다():
    # title에는 한글 잔존, summary에는 지어낸 숫자를 동시에 심어도 title이
    # work_title·location_name보다 먼저 검사되므로 hangul_residue가 보고된다.
    translated = {
        **_en(),
        "title": "2026 도쿄 Comic Market",
        "summary": "Held on October 25",
    }

    assert quarantine_reason("en", _source(), translated) == "hangul_residue"
