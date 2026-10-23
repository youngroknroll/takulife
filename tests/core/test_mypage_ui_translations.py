"""트랙 43-3: 마이페이지 색인 행의 번역 계약.

색인 행의 제목·설명·배지·단위가 요청 언어를 따른다. 행 1·2(내 컬렉션·내 활동)의
`domain_label`은 제목과 겹치므로 어느 언어에서도 빈 문자열이어야 한다(번역 후에도
스크린리더가 제목을 두 번 읽지 않게). 단위는 개수에 따라 단수·복수가 갈린다.
한국어 요청은 현재 출력과 글자 단위로 같다(불변 핀).
"""
import re
from datetime import date
from html.parser import HTMLParser

import pytest
from django.test import Client

from archive.models import CollectionItem, EventInterest, PersonalEntry, UserEventStatus, VisitRecord

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
_MYPAGE_URL = "/mypage/"

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


def _get(user, lang):
    client = Client()
    client.force_login(user)
    return client.get(_MYPAGE_URL, **_LANG_HEADERS[lang])


def _texts(root, cls):
    return [el.text() for el in root.find_all("span", cls)]


def _seed(user, make_event, count):
    """다섯 색인 행의 개수가 모두 `count`가 되도록 데이터를 만든다."""
    for index in range(count):
        event = make_event(title=f"행사 {index}")
        UserEventStatus.objects.create(
            user=user, event=event, status=UserEventStatus.Status.PLANNED
        )
        VisitRecord.objects.create(user=user, event=event, visited_on=date(2026, 6, 1))
        EventInterest.objects.create(user=user, event=event)
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title=f"개인 {index}"
        )
        CollectionItem.objects.create(user=user, name=f"굿즈 {index}")


_UNITS = {
    ("ko", 1): ["점", "건", "건", "곳", "건"],
    ("ko", 2): ["점", "건", "건", "곳", "건"],
    ("en", 1): ["item", "item", "item", "place", "item"],
    ("en", 2): ["items", "items", "items", "places", "items"],
}


# Red 예측: en은 한국어 단위라 Red, ko는 Green 핀, ja·zh는 한글 부재만 단언.
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_색인_행의_단위는_요청_언어와_개수에_맞는_단수_복수다(
    make_user, make_event, lang, count
):
    user = make_user()
    _seed(user, make_event, count)

    resp = _get(user, lang)

    context_units = [row["unit"] for row in resp.context["index_rows"]]
    rendered_units = _texts(_parse(resp), "mypage-index-unit")
    assert [row["count"] for row in resp.context["index_rows"]] == [count] * 5
    if lang in ("ko", "en"):
        assert context_units == _UNITS[(lang, count)]
        assert rendered_units == _UNITS[(lang, count)]
    else:
        assert [u for u in context_units if _KOREAN_RE.search(u)] == []
        assert [u for u in rendered_units if _KOREAN_RE.search(u)] == []
        assert all(context_units)


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_내_컬렉션과_내_활동_행의_배지_라벨은_어느_언어에서도_비어_있다(make_user, lang):
    user = make_user()

    resp = _get(user, lang)

    labels = [row["domain_label"] for row in resp.context["index_rows"]]
    assert labels[0] == ""
    assert labels[1] == ""


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_나머지_세_행은_배지_라벨을_가지고_렌더된다(make_user, lang):
    user = make_user()

    resp = _get(user, lang)

    labels = [row["domain_label"] for row in resp.context["index_rows"]]
    badges = _texts(_parse(resp), "mypage-index-badge")
    assert all(labels[2:])
    assert len(badges) == 3
    if lang == "ko":
        assert labels[2:] == ["내 활동", "내 활동", "내 활동"]
        assert badges == ["내 활동", "내 활동", "내 활동"]
    else:
        assert [b for b in badges if _KOREAN_RE.search(b)] == []


def test_한국어_색인_행의_제목과_설명은_현재_문구_그대로다(make_user):
    user = make_user()

    resp = _get(user, "ko")

    rows = [(r["title"], r["description"]) for r in resp.context["index_rows"]]
    assert rows == [
        ("내 컬렉션", "모은 굿즈를 한눈에 확인해요"),
        ("내 활동", "저장한 행사를 모아봐요"),
        ("다녀온 기록", "다녀온 행사를 기록해요"),
        ("직접 등록", "비공식 장소·행사를 등록해요"),
        ("찜 목록", "관심 있는 행사를 찜해요"),
    ]
    assert _texts(_parse(resp), "mypage-index-title") == [t for t, _ in rows]


@pytest.mark.parametrize("lang", _FOREIGN_LANGS)
def test_외국어_색인_행의_제목과_설명에는_한글이_없다(make_user, lang):
    user = make_user()

    resp = _get(user, lang)

    root = _parse(resp)
    texts = (
        _texts(root, "mypage-index-title")
        + _texts(root, "mypage-index-desc")
        + [r["title"] for r in resp.context["index_rows"]]
        + [r["description"] for r in resp.context["index_rows"]]
    )
    assert len(texts) == 20
    assert [t for t in texts if _KOREAN_RE.search(t)] == []


def test_영어_색인_행의_첫_두_제목은_이미_있는_번역이다(make_user):
    user = make_user()

    resp = _get(user, "en")

    titles = [r["title"] for r in resp.context["index_rows"]]
    assert titles[:2] == ["My collection", "My activity"]
    assert _texts(_parse(resp), "mypage-index-title")[:2] == ["My collection", "My activity"]
