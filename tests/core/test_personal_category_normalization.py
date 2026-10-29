"""트랙 43-3: 개인 항목 분류·굿즈 유형 정규화 순수 함수 계약.

저장값은 언어와 무관한 한국어 원문이어야 한다. 사용자가 어느 언어의 칩 문구를
보냈든 `normalize_*`가 한국어 원문으로 되돌리고, `*_label`은 저장된 원문이
어휘일 때만 요청 언어로 번역한다. 번역 기대값은 리터럴이며 호출 전에 지연
번역을 평가하지 않는다(docs/BE/i18n.md 가드레일 21).
"""

import unicodedata

from django.utils import translation
import pytest

from core.vocab import (
    collection_item_type_label,
    normalize_collection_item_type,
    normalize_personal_category,
    personal_category_label,
)

pytestmark = pytest.mark.contract

_PERSONAL = {
    "ko": ["카페", "팝업스토어", "전시", "성지순례", "굿즈숍", "기타"],
    "en": ["Café", "Pop-up store", "Exhibition", "Pilgrimage site", "Goods shop", "Other"],
    "ja": ["カフェ", "ポップアップストア", "展示", "聖地巡礼", "グッズショップ", "その他"],
    "zh-hans": ["咖啡馆", "快闪店", "展览", "圣地巡礼", "周边商店", "其他"],
}

_GOODS = {
    "ko": ["아크릴 스탠드", "키링", "뱃지", "포토카드", "인형", "문구", "기타"],
    "en": ["Acrylic stand", "Keychain", "Badge", "Photocard", "Plush", "Stationery", "Other"],
    "ja": [
        "アクリルスタンド",
        "キーホルダー",
        "バッジ",
        "フォトカード",
        "ぬいぐるみ",
        "文房具",
        "その他",
    ],
    "zh-hans": ["亚克力立牌", "钥匙扣", "徽章", "小卡", "玩偶", "文具", "其他"],
}


def _cases(table):
    source = table["ko"]
    return [
        pytest.param(lang, translated, source[index], id=f"{lang}-{translated}")
        for lang, labels in table.items()
        for index, translated in enumerate(labels)
    ]


def _fold(text):
    decomposed = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# --- 개인 항목 분류 ---------------------------------------------------------


@pytest.mark.parametrize(
    "typed, expected",
    [("pop-up STORE ", "팝업스토어"), ("Cafe", "카페"), ("CAFÉ", "카페")],
)
def test_대소문자_앞뒤_공백_악센트를_무시하고_분류_원문으로_정규화한다(typed, expected):
    assert normalize_personal_category(typed) == expected


@pytest.mark.parametrize("lang, translated, source", _cases(_PERSONAL))
def test_네_언어의_제안_칩_문구는_모두_한국어_분류_원문으로_돌아간다(lang, translated, source):
    assert normalize_personal_category(translated) == source


def test_일본어_탁점이_빠진_입력은_악센트로_보지_않고_원문으로_바꾸지_않는다():
    # 악센트 무시는 라틴 문자에만 적용한다. 결합 문자를 전부 지우면
    # ポ(탁점 없는 ホ + 반탁점)가 ホ로 접혀 다른 글자가 같은 키가 된다.
    assert normalize_personal_category("ホップアップストア") == "ホップアップストア"


@pytest.mark.parametrize("typed", ["내 분류", "Fashion", ""])
def test_어휘에_없는_분류_자유_입력은_그대로_둔다(typed):
    assert normalize_personal_category(typed) == typed


def test_분류_어휘는_접은_키가_서로_다른_원문끼리_겹치지_않는다():
    keys = {}
    for lang, labels in _PERSONAL.items():
        for index, label in enumerate(labels):
            source = _PERSONAL["ko"][index]
            assert keys.setdefault(_fold(label), source) == source, (lang, label)


@pytest.mark.parametrize(
    "lang, value, expected",
    [
        ("ko", "카페", "카페"),
        ("en", "카페", "Café"),
        ("en", "팝업스토어", "Pop-up store"),
        ("ja", "전시", "展示"),
        ("zh-hans", "성지순례", "圣地巡礼"),
    ],
)
def test_저장된_분류_원문이_어휘이면_요청_언어로_번역해_보여준다(lang, value, expected):
    with translation.override(lang):
        assert personal_category_label(value) == expected


@pytest.mark.parametrize("value", ["종료", "기타 메모", ""])
def test_어휘_밖_분류_값은_영어_요청에서도_번역하지_않고_그대로_보여준다(value):
    with translation.override("en"):
        assert personal_category_label(value) == value


# --- 굿즈 유형 ---------------------------------------------------------------


@pytest.mark.parametrize("lang, translated, source", _cases(_GOODS))
def test_네_언어의_굿즈_유형_문구는_모두_한국어_원문으로_돌아간다(lang, translated, source):
    assert normalize_collection_item_type(translated) == source


@pytest.mark.parametrize(
    "typed, expected",
    [("  KEYCHAIN ", "키링"), ("photocard", "포토카드")],
)
def test_굿즈_유형도_대소문자와_공백을_무시하고_원문으로_정규화한다(typed, expected):
    assert normalize_collection_item_type(typed) == expected


@pytest.mark.parametrize("typed", ["내 유형", "Sticker", ""])
def test_어휘에_없는_굿즈_유형_자유_입력은_그대로_둔다(typed):
    assert normalize_collection_item_type(typed) == typed


def test_굿즈_유형_어휘는_접은_키가_서로_다른_원문끼리_겹치지_않는다():
    keys = {}
    for lang, labels in _GOODS.items():
        for index, label in enumerate(labels):
            source = _GOODS["ko"][index]
            assert keys.setdefault(_fold(label), source) == source, (lang, label)


@pytest.mark.parametrize(
    "lang, value, expected",
    [
        ("ko", "키링", "키링"),
        ("en", "키링", "Keychain"),
        ("ja", "인형", "ぬいぐるみ"),
        ("zh-hans", "문구", "文具"),
    ],
)
def test_저장된_굿즈_유형_원문이_어휘이면_요청_언어로_번역해_보여준다(lang, value, expected):
    with translation.override(lang):
        assert collection_item_type_label(value) == expected


@pytest.mark.parametrize("value", ["종료", "키링 세트", ""])
def test_어휘_밖_굿즈_유형은_영어_요청에서도_번역하지_않고_그대로_보여준다(value):
    with translation.override("en"):
        assert collection_item_type_label(value) == value


# --- 활성 언어 누수 ----------------------------------------------------------


@pytest.mark.parametrize("start_language", ["ko", "en"])
def test_정규화_함수를_호출해도_활성_언어가_바뀌지_않는다(start_language):
    translation.activate(start_language)
    before = translation.get_language()

    normalize_personal_category("Pop-up store")
    normalize_collection_item_type("Keychain")
    personal_category_label("카페")
    collection_item_type_label("키링")

    assert translation.get_language() == before
