"""트랙 43-3 후속: 영어 화면의 잠긴 방문 대상·방문 기록 라벨에서 공식 행사의 한글
제목은 `lang="ko"` 안에 있고, 사용자가 입력한 개인 항목 제목은 태그하지 않는다
(docs/BE/i18n.md 가드레일 16). 대상은 세 곳이다: 방문 기록 작성 잠긴 대상,
컬렉션 작성 잠긴 방문 기록, 컬렉션 수정의 연결된 방문 기록.

`tests`에 `__init__.py`가 없어 파일 간 임포트가 불안정하므로, 요소 트리 파서는
`tests/core/test_archive_ui_leak_scan.py`에서 필요한 최소분만 복제했다.
"""

from html.parser import HTMLParser

import pytest

pytestmark = pytest.mark.web

_OFFICIAL = "공식 한글 제목"
_PERSONAL = "개인 한글 제목"
_VISITED_ON = "2026-05-01"
_EN = {"HTTP_ACCEPT_LANGUAGE": "en"}
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

    def iter_elements(self):
        for part in self.parts:
            if not isinstance(part, str):
                yield part
                yield from part.iter_elements()

    def iter_text_nodes(self):
        for part in self.parts:
            if isinstance(part, str):
                yield part, self
            else:
                yield from part.iter_text_nodes()

    def text(self):
        pieces = [p if isinstance(p, str) else p.text() for p in self.parts]
        return " ".join("".join(pieces).split())


class _TreeParser(HTMLParser):
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
        if self._stack[-1].tag not in _RAW_TEXT_TAGS:
            self._stack[-1].parts.append(data)


def _parse(resp):
    parser = _TreeParser()
    parser.feed(resp.content.decode())
    parser.close()
    return parser.root


def _locked(resp, css_class):
    found = [e for e in _parse(resp).iter_elements() if css_class in e.classes]
    assert len(found) == 1
    return found[0]


def _title_owner(locked, title):
    owners = [owner for text, owner in locked.iter_text_nodes() if title in text]
    assert len(owners) == 1
    return owners[0]


def _has_ko_ancestor(element):
    while element is not None:
        if element.attrs.get("lang") == "ko":
            return True
        element = element.parent
    return False


def _has_lang_below_root(element):
    while element is not None:
        if element.tag != "html" and "lang" in element.attrs:
            return True
        element = element.parent
    return False


def _assert_official_tagged(locked, title):
    assert _has_ko_ancestor(_title_owner(locked, title))


def _assert_personal_untagged(locked, title):
    assert not _has_lang_below_root(_title_owner(locked, title))


@pytest.fixture
def official_visit(user_client, make_event, make_visit):
    user, client = user_client()
    event = make_event(title=_OFFICIAL)
    return client, event, make_visit(user, event=event, visited_on=_VISITED_ON)


@pytest.fixture
def personal_visit(user_client, make_entry, make_visit):
    user, client = user_client()
    entry = make_entry(user, title=_PERSONAL)
    return client, entry, make_visit(user, personal_entry=entry, visited_on=_VISITED_ON)


# (1) 방문 기록 작성: 잠긴 대상
def test_영어_방문_작성의_잠긴_대상은_공식_행사_제목을_lang_ko로_감싼다(official_visit):
    client, event, _ = official_visit

    resp = client.get(f"/archive/visits/new/?subject=event:{event.pk}", **_EN)

    assert resp.status_code == 200
    _assert_official_tagged(_locked(resp, "locked-subject"), _OFFICIAL)


def test_영어_방문_작성의_잠긴_대상은_개인_항목_제목에_lang을_붙이지_않는다(personal_visit):
    client, entry, _ = personal_visit

    resp = client.get(f"/archive/visits/new/?subject=personal:{entry.pk}", **_EN)

    assert resp.status_code == 200
    _assert_personal_untagged(_locked(resp, "locked-subject"), _PERSONAL)


# (2) 컬렉션 작성: 잠긴 방문 기록
def test_영어_컬렉션_작성의_잠긴_방문_기록은_공식_행사_제목만_lang_ko로_감싼다(official_visit):
    client, _, record = official_visit

    resp = client.get(f"/collection/new/?visit_record={record.pk}", **_EN)

    assert resp.status_code == 200
    locked = _locked(resp, "collection-form-locked-label")
    _assert_official_tagged(locked, _OFFICIAL)
    assert not _has_ko_ancestor(_title_owner(locked, _VISITED_ON))


def test_영어_컬렉션_작성의_잠긴_방문_기록은_개인_항목_제목에_lang을_붙이지_않는다(personal_visit):
    client, _, record = personal_visit

    resp = client.get(f"/collection/new/?visit_record={record.pk}", **_EN)

    assert resp.status_code == 200
    _assert_personal_untagged(_locked(resp, "collection-form-locked-label"), _PERSONAL)


def test_한국어_컬렉션_작성의_잠긴_방문_기록은_제목_날짜_텍스트가_그대로다(official_visit):
    client, _, record = official_visit

    resp = client.get(f"/collection/new/?visit_record={record.pk}")

    assert resp.status_code == 200
    locked = _locked(resp, "collection-form-locked-label")
    assert locked.text() == f"{_OFFICIAL} · {_VISITED_ON}"


# (3) 컬렉션 수정: 연결된 방문 기록
def test_영어_컬렉션_수정의_연결된_방문_기록은_공식_행사_제목을_lang_ko로_감싼다(
    official_visit, make_collection_item
):
    client, _, record = official_visit
    item = make_collection_item(record.user, visit_record=record)

    resp = client.get(f"/collection/{item.pk}/edit/", **_EN)

    assert resp.status_code == 200
    _assert_official_tagged(_locked(resp, "collection-edit-visit-label"), _OFFICIAL)


def test_영어_컬렉션_수정의_연결된_방문_기록은_개인_항목_제목에_lang을_붙이지_않는다(
    personal_visit, make_collection_item
):
    client, _, record = personal_visit
    item = make_collection_item(record.user, visit_record=record)

    resp = client.get(f"/collection/{item.pk}/edit/", **_EN)

    assert resp.status_code == 200
    _assert_personal_untagged(_locked(resp, "collection-edit-visit-label"), _PERSONAL)
