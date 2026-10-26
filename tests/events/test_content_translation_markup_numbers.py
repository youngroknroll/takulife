"""events.content_translation.quarantine_reason의 마크업·통화·숫자 규칙에
대한 단위 테스트. 언어는 en 고정 — 이 규칙들은 언어별 문자 판정과 무관하다.
"""
import pytest

from events.content_translation import quarantine_reason

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


@pytest.mark.parametrize(
    "summary",
    [
        "Held on <script>alert(1)</script>",
        "See https://evil.example",
        "Contact a@b.com",
    ],
    ids=["script_tag", "url", "email"],
)
def test_원문에_없는_태그_URL_이메일이_있으면_격리된다(summary):
    assert quarantine_reason("en", _source(), _en(summary=summary)) == "unexpected_markup"


def test_원문에_있던_URL이_번역에_그대로_있으면_통과한다():
    source = _source(summary="자세한 내용 https://example.com/info")
    translated = _en(summary="Details at https://example.com/info")

    assert quarantine_reason("en", source, translated) is None


def test_숫자가_단어로_바뀌어도_원문_숫자의_부분집합이면_통과한다():
    # "10월 24일"의 10이 사라지고 24만 영어 서수로 남아도 통과해야 한다.
    assert quarantine_reason("en", _source(), _en()) is None


def test_원문에_없는_숫자가_생기면_격리된다():
    translated = _en(summary="Held on October 25")

    assert quarantine_reason("en", _source(), translated) == "number_invented"


def test_네_자리_이상_숫자가_번역에서_빠지면_격리된다():
    translated = _en(title="Tokyo Comic Market")

    assert quarantine_reason("en", _source(), translated) == "number_missing"


def test_전각_숫자_원문에_있으면_정규화_후_같은_숫자로_본다():
    source = _source(title="２０２６ 도쿄")
    translated = _en(title="2026 Tokyo")

    assert quarantine_reason("en", source, translated) is None


def test_전각_숫자_번역에_있으면_정규화_후_같은_숫자로_본다():
    source = _source(title="2026 도쿄")
    translated = _en(title="２０２６ Tokyo")

    assert quarantine_reason("en", source, translated) is None


def test_네_자리_미만_숫자의_누락은_격리하지_않는다():
    source = _source(summary="3회 개최")
    translated = _en(summary="Held several times")

    assert quarantine_reason("en", source, translated) is None


def test_쉼표_천단위_표기는_같은_숫자로_본다():
    source = _source(summary="입장료 50000원")
    translated = _en(summary="Admission KRW 50,000")

    assert quarantine_reason("en", source, translated) is None


def test_통화_기호만_바뀐_번역은_격리된다():
    source = _source(summary="입장료 50000원")
    translated = _en(summary="Admission $50,000")

    assert quarantine_reason("en", source, translated) == "currency_changed"


def test_원문에_같은_통화_기호가_있으면_통과한다():
    source = _source(summary="입장료 $50")
    translated = _en(summary="Admission $50")

    assert quarantine_reason("en", source, translated) is None


def test_환산한_금액도_격리된다():
    source = _source(summary="입장료 50000원")
    translated = _en(summary="Admission about $50")

    assert quarantine_reason("en", source, translated) == "currency_changed"


@pytest.mark.parametrize(
    "summary",
    [
        "Admission USD 50",
        "Admission EUR 50",
        "Admission GBP 50",
        "Admission JPY 5000",
        "Admission CNY 50",
        "Admission RMB 50",
        "Admission US$50",
        "Admission €50",
        "Admission £50",
        "Admission ¥5000",
        "Admission 5000円",
    ],
    ids=[
        "usd_코드",
        "eur_코드",
        "gbp_코드",
        "jpy_코드",
        "cny_코드",
        "rmb_코드",
        "us_달러_기호",
        "유로_기호",
        "파운드_기호",
        "엔_기호",
        "엔_한자",
    ],
)
def test_통화_코드와_기호_종류별로_격리된다(summary):
    # 원문에 없는 통화 표기는 숫자가 맞든 안 맞든 통화 규칙이 숫자 규칙보다
    # 먼저 걸려 currency_changed로 격리된다.
    source = _source(summary="입장료 50000원")

    assert quarantine_reason("en", source, _en(summary=summary)) == "currency_changed"
