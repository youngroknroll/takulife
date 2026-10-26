"""events.content_translation.quarantine_reason의 제어문자·길이·빈 칸·
한글 잔존·언어별 문자 판정 규칙에 대한 단위 테스트.
"""
import unicodedata

import pytest

from events.content_translation import TARGET_LANGUAGES, quarantine_reason

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


@pytest.mark.parametrize(
    "summary, expected",
    [("東京国際展示場開催期", None), ("東京国際展示場開催期間", "wrong_script")],
    ids=["열_자_한자만_통과", "열한_자_한자만_격리"],
)
def test_일본어_번역이_열한_자_이상이면_한자만으로는_격리된다(summary, expected):
    translated = _ja(summary=summary)

    assert quarantine_reason("ja", _source(), translated) == expected


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


def test_ASCII_우회는_번역이_원문과_다르면_적용되지_않는다():
    source = _source(work_title="BTS")
    translated = _ja(work_title="Bangtan")

    assert quarantine_reason("ja", source, translated) == "wrong_script"


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
def test_빈_칸_규칙(source_work_title, translated_work_title, expected):
    source = _source(work_title=source_work_title)
    translated = _en(work_title=translated_work_title)

    assert quarantine_reason("en", source, translated) == expected
