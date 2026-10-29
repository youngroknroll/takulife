"""events.content_translation.quarantine_reason의 제어문자·길이·빈 칸·
한글 잔존·언어별 문자 판정 규칙에 대한 단위 테스트.
"""

import re
import unicodedata

import pytest

from events.content_translation import FIELD_MAX_LENGTH, TARGET_LANGUAGES, quarantine_reason

pytestmark = pytest.mark.unit


def _source(**overrides):
    base = {
        "title": "2026 도쿄 코믹마켓",
        "work_title": "원피스",
        "location_name": "도쿄 빅사이트",
        "summary": "10월 24일 개최",
    }
    return {**base, **overrides}


def _en(**overrides):
    base = {
        "title": "2026 Tokyo Comic Market",
        "work_title": "One Piece",
        "location_name": "Tokyo Big Sight",
        "summary": "Held on October 24",
    }
    return {**base, **overrides}


def _ja(**overrides):
    base = {
        "title": "2026 東京コミックマーケット",
        "work_title": "ワンピース",
        "location_name": "東京ビッグサイト",
        "summary": "10月24日開催",
    }
    return {**base, **overrides}


def _zh(**overrides):
    base = {
        "title": "2026 东京漫展",
        "work_title": "海贼王",
        "location_name": "东京国际展览中心",
        "summary": "10月24日举办",
    }
    return {**base, **overrides}


def _base(language):
    return {"en": _en(), "ja": _ja(), "zh-hans": _zh()}[language]


def test_영어_번역에_라틴_문자가_없으면_격리된다():
    translated = _en(title="2026 東京コミケ")

    assert quarantine_reason("en", _source(), translated) == "wrong_script"


def test_일본어_번역에_가나도_한자도_없으면_격리된다():
    translated = _ja(title="2026 Tokyo Comic Market")

    assert quarantine_reason("ja", _source(), translated) == "wrong_script"


def test_일본어_번역이_열_자_이하이고_한자만_있으면_통과한다():
    translated = _ja(location_name="東京")

    assert quarantine_reason("ja", _source(), translated) is None


def test_일본어_번역이_정확히_열_자이고_한자만이면_통과한다():
    translated = _ja(summary="東京国際展示場開催期")

    assert quarantine_reason("ja", _source(), translated) is None


def test_일본어_번역이_열한_자이고_한자만이면_격리된다():
    translated = _ja(summary="東京国際展示場開催期間")

    assert quarantine_reason("ja", _source(), translated) == "wrong_script"


def test_중국어_간체_번역에_가나가_섞이면_격리된다():
    translated = _zh(title="2026 东京コミケ")

    assert quarantine_reason("zh-hans", _source(), translated) == "wrong_script"


def test_중국어_간체_번역에_한자가_없으면_격리된다():
    translated = _zh(title="2026 Tokyo Comic Market")

    assert quarantine_reason("zh-hans", _source(), translated) == "wrong_script"


@pytest.mark.parametrize("language", TARGET_LANGUAGES)
def test_원문이_ASCII뿐이고_번역이_같으면_세_언어_모두_통과한다(language):
    source = _source(work_title="BTS")
    translated = {**_base(language), "work_title": "BTS"}

    assert quarantine_reason(language, source, translated) is None


@pytest.mark.parametrize("language", TARGET_LANGUAGES)
@pytest.mark.parametrize(
    "field_name, value",
    [("title", "BTS"), ("summary", "LIVE")],
    ids=["title", "summary"],
)
def test_원문이_ASCII뿐인_제목과_요약은_같은_번역이면_세_언어_모두_통과한다(
    language, field_name, value
):
    # 고유명사 라틴 예외는 work_title·location_name에만 적용돼, title·
    # summary의 ASCII 동일 번역 우회는 그 예외와 무관하게 따로 지켜야
    # 한다(work_title 버전은 예외만으로도 통과해 우회 분기를 더는
    # 구분하지 못한다).
    source = _source(**{field_name: value})
    translated = {**_base(language), field_name: value}

    assert quarantine_reason(language, source, translated) is None


def test_ASCII_우회는_번역이_원문과_다르면_적용되지_않는다():
    # work_title은 고유명사 라틴 예외 대상이라, 그 예외가 없는 title로 옮겨
    # "ASCII 원문 동일 번역 우회는 번역이 원문과 다르면 적용되지 않는다"는
    # 본래 의도를 계속 지킨다.
    source = _source(title="BTS")
    translated = _ja(title="Bangtan")

    assert quarantine_reason("ja", source, translated) == "wrong_script"


def test_고유명사_필드의_라틴_문자_번역은_일본어에서도_통과한다():
    # 공식 표기가 라틴 문자인 고유명사(작품명)는 일본어에서도 가나·한자
    # 없이 라틴 문자만으로 통과해야 한다 — 실기동 오탐(이벤트 8,
    # "스파이 패밀리" → "SPY×FAMILY") 보정.
    source = _source(work_title="스파이 패밀리")
    translated = _ja(work_title="SPY×FAMILY")

    assert quarantine_reason("ja", source, translated) is None


def test_고유명사_필드의_라틴_문자_번역은_중국어_간체에서도_통과한다():
    # 같은 예외를 중국어 간체에서도 확인한다 — 실기동 오탐(이벤트 7,
    # "스타필드 하남" → "Starfield Hanam") 보정.
    source = _source(location_name="스타필드 하남")
    translated = _zh(location_name="Starfield Hanam")

    assert quarantine_reason("zh-hans", source, translated) is None


@pytest.mark.parametrize("language", ["ja", "zh-hans"])
def test_고유명사_필드라도_라틴_문자가_없으면_예외가_적용되지_않는다(language):
    # 고유명사 라틴 예외는 "라틴 문자를 포함"해야 성립한다 — 기호뿐인
    # 번역(라틴·가나·한자 모두 없음)은 예외 대상이 아니라 그대로 격리돼야
    # 한다.
    source = _source(work_title="스파이 패밀리")
    translated = {**_base(language), "work_title": "☆☆☆"}

    assert quarantine_reason(language, source, translated) == "wrong_script"


def test_고유명사_필드라도_한자가_섞인_긴_일본어_표기는_예외가_적용되지_않는다():
    # 고유명사 라틴 예외는 "한자가 하나도 없어야" 성립한다 — 라틴과 한자가
    # 섞이고 가나가 없는 11자 이상(공백 제외) 표기는 일본어 짧은-한자만
    # 통과 규칙(10자 이하)에도 못 들어 그대로 격리돼야 한다.
    translated = "Starfield 河南市役所本館事務所"
    assert len(re.sub(r"\s+", "", translated)) >= 11

    source = _source(location_name="스타필드 하남")
    translated_fields = _ja(location_name=translated)

    assert quarantine_reason("ja", source, translated_fields) == "wrong_script"


@pytest.mark.parametrize("language", ["ja", "zh-hans"])
@pytest.mark.parametrize(
    "field_name, source_value, translated_value",
    [
        ("title", "2026 도쿄 코믹마켓", "2026 Tokyo Comic Market"),
        ("summary", "10월 24일 개최", "Held on October 24"),
    ],
    ids=["title", "summary"],
)
def test_제목과_요약이_라틴_문자만이면_일본어_중국어에서_여전히_격리된다(
    language, field_name, source_value, translated_value
):
    # 고유명사 라틴 예외는 work_title·location_name에만 적용된다 — title·
    # summary가 통째로 영어로 나온 응답은 계속 잡아야 한다.
    source = _source(**{field_name: source_value})
    translated = {**_base(language), field_name: translated_value}

    assert quarantine_reason(language, source, translated) == "wrong_script"


def test_고유명사_필드라도_가나가_섞인_중국어는_격리된다():
    # 번역에 가나가 섞이면 "라틴 문자만"이라는 예외 조건이 깨져, 중국어
    # 간체의 가나 금지 규칙이 그대로 적용돼야 한다.
    source = _source(work_title="스파이 패밀리")
    translated = _zh(work_title="SPY×ファミリー")

    assert quarantine_reason("zh-hans", source, translated) == "wrong_script"


def test_한글_음절이_남으면_격리된다():
    translated = _en(title="2026 도쿄 Comic Market")

    assert quarantine_reason("en", _source(), translated) == "hangul_residue"


def test_분해된_한글_자모가_남아도_격리된다():
    nfd_title = "2026 " + unicodedata.normalize("NFD", "도쿄") + " Comic Market"
    translated = _en(title=nfd_title)

    assert quarantine_reason("en", _source(), translated) == "hangul_residue"


@pytest.mark.parametrize(
    "ctrl_char",
    ["\u202e", "\u200b", "\ufeff"],
    ids=["우측_정렬_재정의", "폭_없는_공백", "바이트_순서_표시"],
)
def test_방향_제어_제로폭_문자가_있으면_격리된다(ctrl_char):
    translated = _en(title="Tokyo" + ctrl_char + " Comic Market")

    assert quarantine_reason("en", _source(), translated) == "control_char"


def test_BEL과_같은_제어문자는_격리된다():
    translated = _en(summary="Held on October 24\x07")

    assert quarantine_reason("en", _source(), translated) == "control_char"


@pytest.mark.parametrize("whitespace", ["\n", "\t"], ids=["줄바꿈", "탭"])
def test_줄바꿈과_탭은_격리하지_않는다(whitespace):
    translated = _en(summary="Held on October 24" + whitespace)

    assert quarantine_reason("en", _source(), translated) is None


@pytest.mark.parametrize(
    "field_name, filler_len, ok_len, over_len",
    [
        ("title", 100, 400, 401),
        ("work_title", 100, 400, 401),
        ("location_name", 100, 400, 401),
        ("summary", 400, 2000, 2001),
    ],
)
def test_절대_길이_상한을_넘으면_격리된다(field_name, filler_len, ok_len, over_len):
    # 상대 상한(6×원문 길이)이 걸리지 않도록 원문을 충분히 길게 채워 절대
    # 상한만 단독으로 측정한다.
    source = _source(**{field_name: "가" * filler_len})

    ok = quarantine_reason("en", source, _en(**{field_name: "A" * ok_len}))
    over = quarantine_reason("en", source, _en(**{field_name: "A" * over_len}))

    assert ok is None
    assert over == "too_long"


def test_상한을_넘는_문자열은_제어문자가_섞여도_too_long이다():
    # 원문을 충분히 길게 둬서(기존 test_절대_길이_상한을_넘으면_격리된다의
    # title 필러와 같은 길이) 상대 상한(6×원문 길이)에 먼저 걸리지 않게 한다.
    source = _source(title="가" * 100)
    translated = _en(title="A" * 401 + chr(7))

    assert quarantine_reason("en", source, translated) == "too_long"


def test_원문_대비_상대_상한을_넘으면_격리된다():
    # 원문 title이 2자이면 상한은 max(40, 6*2)=40자다.
    source = _source(title="도쿄")

    ok = quarantine_reason("en", source, _en(title="A" * 40))
    over = quarantine_reason("en", source, _en(title="A" * 41))

    assert ok is None
    assert over == "too_long"


def test_원문_길이에_비례해_상대_상한이_넓어진다():
    # 원문 title이 10자(숫자·공백 없음)이면 상한은 max(40, 6*10)=60자다 —
    # 기존 경계값 테스트는 하한 40에만 걸려 배수 6을 검증하지 못했다.
    source = _source(title="가" * 10)

    ok = quarantine_reason("en", source, _en(title="A" * 60))
    over = quarantine_reason("en", source, _en(title="A" * 61))

    assert ok is None
    assert over == "too_long"


def test_반각_한글이_남아도_격리된다():
    # 반각 한글 자모는 NFKC 정규화 후에야 한글 자모(\u1100 대역)가 된다.
    halfwidth_jamo = "\uffa1\uffa2"
    translated = _en(title="2026 " + halfwidth_jamo + " Comic Market")

    assert quarantine_reason("en", _source(), translated) == "hangul_residue"


@pytest.mark.parametrize(
    "source_work_title, translated_work_title, expected",
    [
        ("", "", None),
        ("", "One Piece", "nonempty_for_empty_source"),
        ("원피스", "", "empty_translation"),
        ("원피스", "   ", "empty_translation"),
    ],
    ids=["둘_다_빈_문자열", "원문만_빈_문자열", "번역이_빈_문자열", "번역이_공백뿐"],
)
def test_원문과_번역의_빈_칸_조합에_따라_사유가_정해진다(
    source_work_title, translated_work_title, expected
):
    source = _source(work_title=source_work_title)
    translated = _en(work_title=translated_work_title)

    assert quarantine_reason("en", source, translated) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("\x0b" * (FIELD_MAX_LENGTH["work_title"] + 1), "too_long"),
        ("\x0b", "control_char"),
        (" \n", None),
    ],
    ids=["수직탭_상한초과", "수직탭_하나", "공백_줄바꿈뿐"],
)
def test_원문이_비었고_번역이_공백_문자뿐이어도_길이와_제어문자_검사가_먼저_돈다(value, expected):
    source = _source(work_title="")
    translated = _en(work_title=value)

    assert quarantine_reason("en", source, translated) == expected


@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("title", "2026 Tokyo" + chr(0xD800) + " Comic Market", "control_char"),
        ("summary", "Held on October 24 " + chr(0x1F600), None),
    ],
    ids=["외톨이_서로게이트", "이모지_정상"],
)
def test_외톨이_서로게이트가_있으면_격리된다(field, value, expected):
    translated = _en(**{field: value})

    assert quarantine_reason("en", _source(), translated) == expected


@pytest.mark.parametrize(
    "value",
    [chr(0xD7) * 2, chr(0xF7) * 2],
    ids=["곱셈_기호", "나눗셈_기호"],
)
def test_영어_번역이_곱셈_나눗셈_기호뿐이면_격리된다(value):
    translated = _en(work_title=value)

    assert quarantine_reason("en", _source(), translated) == "wrong_script"
