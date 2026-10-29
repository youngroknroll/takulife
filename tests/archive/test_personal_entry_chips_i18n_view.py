"""트랙 43-3: 개인 항목 카테고리 칩과 굿즈 유형 칩의 화면 번역 계약.

제안 칩의 텍스트와 `data-*-label` 속성은 요청 언어의 라벨이고, 저장된 한국어
원문이 어휘일 때만 목록·상세·수정 입력창에서 요청 언어로 보인다(어휘 밖 값은
그대로). 방문 목록의 카테고리 칩은 라벨(번역)과 필터 토큰(한국어 원문)을 분리해,
언어를 바꿔도 `?filter=cat:` 값이 한국어 원문으로 같다.
저장 정규화 자체는 tests/archive/test_personal_entry_category_i18n_api.py 소관이다.
"""

from datetime import date
from html.parser import HTMLParser
import re
from urllib.parse import unquote

from django.test import Client
import pytest

pytestmark = [pytest.mark.web, pytest.mark.django_db]

_KOREAN_RE = re.compile(r"[가-힣]")

_LANG_HEADERS = {
    "ko": {},
    "en": {"HTTP_ACCEPT_LANGUAGE": "en"},
    "ja": {"HTTP_ACCEPT_LANGUAGE": "ja"},
    "zh-hans": {"HTTP_ACCEPT_LANGUAGE": "zh-hans"},
}
_ALL_LANGS = ["ko", "en", "ja", "zh-hans"]
_KO_EN = ["ko", "en"]
_FOREIGN_JA_ZH = ["ja", "zh-hans"]

_CATEGORY_CHIPS = {
    "ko": ["카페", "팝업스토어", "전시", "성지순례", "굿즈숍", "기타"],
    "en": ["Café", "Pop-up store", "Exhibition", "Pilgrimage site", "Goods shop", "Other"],
}
_TYPE_CHIPS = {
    "ko": ["아크릴 스탠드", "키링", "뱃지", "포토카드", "인형", "문구", "기타"],
    "en": ["Acrylic stand", "Keychain", "Badge", "Photocard", "Plush", "Stationery", "Other"],
}
_CAFE = {"ko": "카페", "en": "Café"}
_KEYCHAIN = {"ko": "키링", "en": "Keychain"}

_VOID_TAGS = frozenset(
    "br hr img input link meta source wbr area base col embed param track".split()
)
_RAW_TEXT_TAGS = frozenset({"script", "style"})


class _Element:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.parts = []

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()

    def text(self):
        pieces = [p if isinstance(p, str) else p.text() for p in self.parts]
        return " ".join("".join(pieces).split())

    def iter_elements(self):
        for part in self.parts:
            if not isinstance(part, str):
                yield part
                yield from part.iter_elements()

    def find_all(self, tag=None, cls=None, attrs=None):
        found = []
        for element in self.iter_elements():
            if tag is not None and element.tag != tag:
                continue
            if cls is not None and cls not in element.classes:
                continue
            if attrs is not None and any(
                element.attrs.get(key) != value for key, value in attrs.items()
            ):
                continue
            found.append(element)
        return found


class _TreeParser(HTMLParser):
    """void 태그를 스택에 넣지 않는 요소 트리 수집기."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Element("#root", [], None)
        self._stack = [self.root]

    def _attach(self, tag, attrs):
        element = _Element(tag, attrs, self._stack[-1])
        self._stack[-1].parts.append(element)
        return element

    def handle_starttag(self, tag, attrs):
        element = self._attach(tag, attrs)
        if tag not in _VOID_TAGS:
            self._stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self._attach(tag, attrs)

    def handle_endtag(self, tag):
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data):
        current = self._stack[-1]
        if current.tag not in _RAW_TEXT_TAGS:
            current.parts.append(data)


def _parse(resp):
    parser = _TreeParser()
    parser.feed(resp.content.decode())
    parser.close()
    return parser.root


def _get(user, path, lang):
    client = Client()
    client.force_login(user)
    return client.get(path, **_LANG_HEADERS[lang])


def _chips(root, cls, label_attr):
    """칩 버튼들의 (텍스트, data-라벨 속성) 쌍."""
    return [(b.text(), b.attrs.get(label_attr)) for b in root.find_all("button", cls)]


def _input_value(root, input_id):
    found = root.find_all("input", attrs={"id": input_id})
    assert len(found) == 1, f"input#{input_id}: {len(found)}개"
    return found[0].attrs.get("value", "")


def _assert_chips(lang, chips, expected_by_lang):
    texts = [text for text, _ in chips]
    attrs = [attr for _, attr in chips]
    assert attrs == texts, "칩 텍스트와 data 라벨 속성이 갈라졌다"
    if lang in expected_by_lang:
        assert texts == expected_by_lang[lang]
    else:
        assert len(texts) == len(expected_by_lang["ko"])
        assert [t for t in texts if _KOREAN_RE.search(t)] == []


# ---------------------------------------------------------------------------
# 개인 항목 등록·수정 화면의 제안 칩
# ---------------------------------------------------------------------------


# Red 예측: 칩 목록이 이미 지연 번역이면 en은 Green일 수 있다(오케스트레이터 판정).
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_개인_항목_등록_화면의_칩_여섯_개는_요청_언어의_라벨이다(make_user, lang):
    user = make_user()

    resp = _get(user, "/archive/personal/new/", lang)

    chips = _chips(_parse(resp), "personal-form-category-chip", "data-category-label")
    _assert_chips(lang, chips, _CATEGORY_CHIPS)


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_개인_항목_수정_화면의_칩_여섯_개는_요청_언어의_라벨이다(make_user, make_entry, lang):
    user = make_user()
    entry = make_entry(user, category="카페")

    resp = _get(user, f"/archive/personal/{entry.id}/edit/", lang)

    chips = _chips(_parse(resp), "personal-form-category-chip", "data-category-label")
    _assert_chips(lang, chips, _CATEGORY_CHIPS)


@pytest.mark.parametrize("lang", _KO_EN)
def test_수정_입력창은_저장된_어휘_값을_요청_언어_라벨로_채우고_같은_칩이_있다(
    make_user, make_entry, lang
):
    user = make_user()
    entry = make_entry(user, category="카페")

    resp = _get(user, f"/archive/personal/{entry.id}/edit/", lang)

    root = _parse(resp)
    value = _input_value(root, "personal-category")
    chip_labels = [a for _, a in _chips(root, "personal-form-category-chip", "data-category-label")]
    assert value == _CAFE[lang]
    assert value in chip_labels


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_수정_입력창의_어휘_밖_값은_어느_언어에서도_그대로다(make_user, make_entry, lang):
    user = make_user()
    entry = make_entry(user, category="종료")

    resp = _get(user, f"/archive/personal/{entry.id}/edit/", lang)

    assert _input_value(_parse(resp), "personal-category") == "종료"


# ---------------------------------------------------------------------------
# 목록·상세에서 저장된 한국어 원문의 표시
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", _KO_EN)
def test_저장된_카페는_개인_항목_목록_행에서_요청_언어_라벨로_보인다(make_user, make_entry, lang):
    user = make_user()
    make_entry(user, category="카페")

    resp = _get(user, "/archive/personal/", lang)

    cats = _parse(resp).find_all("span", "record-row-cat")
    assert [c.text() for c in cats] == [_CAFE[lang]]


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_어휘_밖_값_종료는_개인_항목_목록_행에서_어느_언어에서도_그대로다(
    make_user, make_entry, lang
):
    user = make_user()
    make_entry(user, category="종료")

    resp = _get(user, "/archive/personal/", lang)

    cats = _parse(resp).find_all("span", "record-row-cat")
    assert [c.text() for c in cats] == ["종료"]


@pytest.mark.parametrize("lang", _KO_EN)
def test_저장된_카페는_개인_항목_상세에서_요청_언어_라벨로_보인다(make_user, make_entry, lang):
    user = make_user()
    entry = make_entry(user, category="카페")

    resp = _get(user, f"/archive/personal/{entry.id}/", lang)

    chips = _parse(resp).find_all("span", "personal-detail-chip")
    # 상세에는 카테고리 칩 뒤에 종류 칩(비공식 장소)이 하나 더 있다.
    assert [c.text() for c in chips][0] == _CAFE[lang]


# ---------------------------------------------------------------------------
# 방문 목록의 개인 항목 카테고리 칩 — 라벨은 번역, 필터 토큰은 한국어 원문
# ---------------------------------------------------------------------------


def _category_filter_chips(root):
    """`?filter=cat:` 링크의 (라벨, 디코딩한 토큰) 쌍."""
    found = []
    for anchor in root.find_all("a"):
        href = anchor.attrs.get("href", "")
        if href.startswith("?filter=cat:"):
            token = unquote(href[len("?filter=cat:") :].split("&")[0])
            found.append((anchor.text(), token))
    return found


@pytest.mark.parametrize("lang", _KO_EN)
def test_방문_목록의_개인_항목_카테고리_칩은_번역_라벨과_한국어_토큰으로_갈린다(
    make_user, make_entry, make_visit, lang
):
    user = make_user()
    entry = make_entry(user, category="카페")
    make_visit(user, personal_entry=entry, visited_on=date(2026, 5, 1))

    resp = _get(user, "/archive/visits/", lang)

    assert _category_filter_chips(_parse(resp)) == [(_CAFE[lang], "카페")]
    assert [chip["token"] for chip in resp.context["category_chips"]] == ["카페"]


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_방문_목록의_카테고리_필터_토큰은_언어와_무관하게_한국어_원문이다(
    make_user, make_entry, make_visit, lang
):
    user = make_user()
    entry = make_entry(user, category="카페")
    make_visit(user, personal_entry=entry, visited_on=date(2026, 5, 1))

    resp = _get(user, "/archive/visits/", lang)

    tokens = [token for _, token in _category_filter_chips(_parse(resp))]
    assert tokens == ["카페"]
    assert [chip["token"] for chip in resp.context["category_chips"]] == ["카페"]


@pytest.mark.parametrize("lang", _KO_EN)
def test_한국어_토큰_필터는_영어_화면에서도_해당_칩을_활성으로_표시한다(
    make_user, make_entry, make_visit, lang
):
    user = make_user()
    entry = make_entry(user, category="카페", title="필터 대상")
    make_visit(user, personal_entry=entry, visited_on=date(2026, 5, 1))

    resp = _get(user, "/archive/visits/?filter=cat:카페", lang)

    root = _parse(resp)
    active = [
        a.text()
        for a in root.find_all("a", "chip")
        if a.attrs.get("aria-current") == "page"
        and a.attrs.get("href", "").startswith("?filter=cat:")
    ]
    assert active == [_CAFE[lang]]


# ---------------------------------------------------------------------------
# 굿즈 유형 칩 — 개인 항목 칩과 같은 구조
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_굿즈_등록_화면의_유형_칩은_요청_언어의_라벨이다(make_user, lang):
    user = make_user()

    resp = _get(user, "/collection/new/", lang)

    chips = _chips(_parse(resp), "collection-form-type-chip", "data-type-label")
    _assert_chips(lang, chips, _TYPE_CHIPS)


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_굿즈_수정_화면의_유형_칩은_요청_언어의_라벨이다(make_user, make_collection_item, lang):
    user = make_user()
    item = make_collection_item(user, item_type="키링")

    resp = _get(user, f"/collection/{item.pk}/edit/", lang)

    chips = _chips(_parse(resp), "collection-form-type-chip", "data-type-label")
    _assert_chips(lang, chips, _TYPE_CHIPS)


@pytest.mark.parametrize("lang", _KO_EN)
def test_저장된_키링은_굿즈_수정_입력창에서_요청_언어_라벨이고_같은_칩이_있다(
    make_user, make_collection_item, lang
):
    user = make_user()
    item = make_collection_item(user, item_type="키링")

    resp = _get(user, f"/collection/{item.pk}/edit/", lang)

    root = _parse(resp)
    value = _input_value(root, "collection-item-type")
    chip_labels = [a for _, a in _chips(root, "collection-form-type-chip", "data-type-label")]
    assert value == _KEYCHAIN[lang]
    assert value in chip_labels


@pytest.mark.parametrize("lang", _KO_EN)
def test_저장된_키링은_굿즈_목록_행과_상세에서_요청_언어_라벨로_보인다(
    make_user, make_collection_item, lang
):
    user = make_user()
    item = make_collection_item(user, item_type="키링", work_title="Work")

    list_root = _parse(_get(user, "/collection/?view=list", lang))
    detail_root = _parse(_get(user, f"/collection/{item.pk}/", lang))

    assert [e.text() for e in list_root.find_all("p", "collection-row-work")] == [
        f"Work · {_KEYCHAIN[lang]}"
    ]
    assert [e.text() for e in detail_root.find_all("p", "collection-detail-type")] == [
        _KEYCHAIN[lang]
    ]


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_어휘_밖_굿즈_유형은_수정_입력창에서_어느_언어에서도_그대로다(
    make_user, make_collection_item, lang
):
    user = make_user()
    item = make_collection_item(user, item_type="직접입력유형")

    resp = _get(user, f"/collection/{item.pk}/edit/", lang)

    assert _input_value(_parse(resp), "collection-item-type") == "직접입력유형"
