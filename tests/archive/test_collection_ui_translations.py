"""트랙 43-3: 컬렉션 화면의 배지·수량 문구·상세 메타 행 번역 계약.

배지(보유·구함·교환·미보유), 카드의 수량·교환 가능 문구, 굿즈 상세의 메타 행
라벨과 `N개` 값이 요청 언어를 따른다. 한국어 요청은 현재 출력과 글자 단위로
같다(불변 핀). 날짜 값 `%Y.%m.%d`와 사용자 입력(획득 경로)은 번역하지 않는다.
단언은 HTML을 파싱해 요소 단위로 한다.
"""

import re
from datetime import date
from html.parser import HTMLParser

import pytest
from django.test import Client

pytestmark = [pytest.mark.web, pytest.mark.django_db]

_KOREAN_RE = re.compile(r"[가-힣]")

_LANG_HEADERS = {
    "ko": {},
    "en": {"HTTP_ACCEPT_LANGUAGE": "en"},
    "ja": {"HTTP_ACCEPT_LANGUAGE": "ja"},
    "zh-hans": {"HTTP_ACCEPT_LANGUAGE": "zh-hans"},
}
_ALL_LANGS = ["ko", "en", "ja", "zh-hans"]
_FOREIGN_LANGS = ["en", "ja", "zh-hans"]

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


def _texts(elements):
    return [element.text() for element in elements]


def _assert_no_korean(texts):
    assert texts, "검사할 텍스트가 없다"
    assert [t for t in texts if _KOREAN_RE.search(t)] == []


# ---------------------------------------------------------------------------
# 배지 — 뷰 컨텍스트(row.badges)와 렌더(.collection-pill-tag)
# ---------------------------------------------------------------------------

_BADGE_LABELS = {
    "ko": ["보유", "구함", "교환"],
    "en": ["Owned", "Wanted", "Trade"],
}
_NOT_OWNED = {"ko": "미보유", "en": "Not owned"}


# Red 예측: en은 한국어 배지라 Red, ko는 Green 핀. ja·zh는 한글 부재만 단언.
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_보유_구함_교환_배지는_요청_언어의_라벨로_고정_순서로_나온다(
    user_client, make_collection_item, lang
):
    user, _ = user_client()
    make_collection_item(user, quantity=3, tradeable_quantity=2, is_wanted=True)

    resp = _get(user, "/collection/?partial=1", lang)

    row = resp.context["item_rows"][0]
    context_labels = [badge["label"] for badge in row["badges"]]
    rendered = _texts(_parse(resp).find_all("span", "collection-pill-tag"))
    assert [badge["tone"] for badge in row["badges"]] == ["owned", "wanted", "tradeable"]
    if lang in _BADGE_LABELS:
        assert context_labels == _BADGE_LABELS[lang]
        assert rendered == _BADGE_LABELS[lang]
    else:
        _assert_no_korean(context_labels)
        _assert_no_korean(rendered)


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_어느_축도_아닌_항목의_배지는_요청_언어의_미보유_하나다(
    user_client, make_collection_item, lang
):
    user, _ = user_client()
    make_collection_item(user, quantity=0, tradeable_quantity=0, is_wanted=False)

    resp = _get(user, "/collection/?partial=1", lang)

    row = resp.context["item_rows"][0]
    context_labels = [badge["label"] for badge in row["badges"]]
    rendered = _texts(_parse(resp).find_all("span", "collection-pill-tag"))
    assert [badge["tone"] for badge in row["badges"]] == ["none"]
    if lang in _NOT_OWNED:
        assert context_labels == [_NOT_OWNED[lang]]
        assert rendered == [_NOT_OWNED[lang]]
    else:
        _assert_no_korean(context_labels)
        _assert_no_korean(rendered)


# ---------------------------------------------------------------------------
# 카드의 수량·교환 가능 문구
# ---------------------------------------------------------------------------

_QUANTITY_LABELS = {
    "ko": ("수량 3개", "교환 가능 2개"),
    "en": ("Quantity: 3", "Tradeable: 2"),
}


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_카드의_수량과_교환_가능_문구는_요청_언어의_문장이다(
    user_client, make_collection_item, lang
):
    user, _ = user_client()
    make_collection_item(user, quantity=3, tradeable_quantity=2)

    resp = _get(user, "/collection/?partial=1", lang)

    row = resp.context["item_rows"][0]
    # 기본 격자 보기는 gcard-meta, 목록 보기는 collection-row-meta에 같은 문구를 싣는다.
    meta_texts = _texts(_parse(resp).find_all("p", "gcard-meta"))
    if lang in _QUANTITY_LABELS:
        quantity_label, tradeable_label = _QUANTITY_LABELS[lang]
        assert row["quantity_label"] == quantity_label
        assert row["tradeable_label"] == tradeable_label
        assert any(quantity_label in text and tradeable_label in text for text in meta_texts)
    else:
        _assert_no_korean([row["quantity_label"], row["tradeable_label"]])


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_수량이_0이면_수량과_교환_가능_문구는_언어와_무관하게_비어_있다(
    user_client, make_collection_item, lang
):
    user, _ = user_client()
    make_collection_item(user, quantity=0, tradeable_quantity=0, is_wanted=True)

    resp = _get(user, "/collection/?partial=1", lang)

    row = resp.context["item_rows"][0]
    assert row["quantity_label"] == ""
    assert row["tradeable_label"] == ""


# ---------------------------------------------------------------------------
# 굿즈 상세 메타 행 — 라벨은 번역, `N개`는 ngettext, 날짜·사용자 입력은 그대로
# ---------------------------------------------------------------------------

_META_LABELS = {
    "ko": ["수량", "교환 가능", "획득일", "획득 경로"],
    "en": ["Quantity", "Tradeable", "Acquired on", "Source"],
}
_META_VALUES = {
    ("ko", 1): ["1개", "1개"],
    ("ko", 2): ["2개", "2개"],
    ("en", 1): ["1 item", "1 item"],
    ("en", 2): ["2 items", "2 items"],
}


def _meta_rows(resp):
    rows = _parse(resp).find_all("div", "collection-detail-meta-row")
    return [(row.find_all("dt")[0].text(), row.find_all("dd")[0].text()) for row in rows]


def _detail_item(make_collection_item, user, count):
    return make_collection_item(
        user,
        quantity=count,
        tradeable_quantity=count,
        acquired_on=date(2026, 3, 5),
        acquisition_source="Pop-up shop",
    )


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_상세_메타_행의_라벨과_개수는_요청_언어를_따른다(
    user_client, make_collection_item, lang, count
):
    user, _ = user_client()
    item = _detail_item(make_collection_item, user, count)

    resp = _get(user, f"/collection/{item.pk}/", lang)

    rows = _meta_rows(resp)
    if lang in _META_LABELS:
        labels = [label for label, _ in rows]
        values = [value for _, value in rows]
        assert labels == _META_LABELS[lang]
        assert values == _META_VALUES[(lang, count)] + ["2026.03.05", "Pop-up shop"]
    else:
        _assert_no_korean([label for label, _ in rows])
        _assert_no_korean([value for _, value in rows[:2]])


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_상세_컨텍스트의_메타_행도_같은_라벨과_값이다(user_client, make_collection_item, lang):
    user, _ = user_client()
    item = _detail_item(make_collection_item, user, 2)

    resp = _get(user, f"/collection/{item.pk}/", lang)

    meta = [(row["label"], row["value"]) for row in resp.context["meta_rows"]]
    if lang in _META_LABELS:
        assert [label for label, _ in meta] == _META_LABELS[lang]
        assert [value for _, value in meta][:2] == _META_VALUES[(lang, 2)]
        assert [value for _, value in meta][2:] == ["2026.03.05", "Pop-up shop"]
    else:
        _assert_no_korean([label for label, _ in meta])
        _assert_no_korean([value for _, value in meta[:2]])
