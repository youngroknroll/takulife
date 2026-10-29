"""트랙 43-2: 이벤트 목록·달력·상세 화면의 UI 다국어 계약.

`.mo`가 로컬에 컴파일돼 있어야 한다(`uv run django-admin compilemessages
--ignore .venv`). 단언은 HTML을 파싱해 요소 단위로 하고, 부분 문자열
`in body` 비교는 쓰지 않는다 — 43-1에서 `"Save" in body`가 `Saved`에 걸려
거짓 통과한 적이 있다.
"""

from datetime import date
from html.parser import HTMLParser
import re

from django.test import Client
import pytest

from archive.models import UserEventStatus

pytestmark = pytest.mark.web

_KOREAN_RE = re.compile(r"[가-힣]")

_LANG_HEADERS = {
    "ko": {},
    "en": {"HTTP_ACCEPT_LANGUAGE": "en"},
    "ja": {"HTTP_ACCEPT_LANGUAGE": "ja"},
    "zh-hans": {"HTTP_ACCEPT_LANGUAGE": "zh-hans"},
}

_VOID_TAGS = frozenset(
    "br hr img input link meta source wbr area base col embed param track".split()
)
_RAW_TEXT_TAGS = frozenset({"script", "style"})
_PRESENT = object()


class _Element:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.parts = []  # str 텍스트 노드와 자식 _Element가 문서 순서대로 섞여 있다
        self.raw_text = ""  # script/style 내용(텍스트 노드로 세지 않는다)

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()

    def text(self, skip=None):
        pieces = []
        for part in self.parts:
            if isinstance(part, str):
                pieces.append(part)
            elif skip is None or not skip(part):
                pieces.append(part.text(skip))
        return " ".join("".join(pieces).split())

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

    def find_all(self, tag=None, cls=None, attrs=None):
        found = []
        for element in self.iter_elements():
            if tag is not None and element.tag != tag:
                continue
            if cls is not None and cls not in element.classes:
                continue
            if attrs is not None and not _attrs_match(element, attrs):
                continue
            found.append(element)
        return found


def _attrs_match(element, attrs):
    for key, expected in attrs.items():
        if key not in element.attrs:
            return False
        if expected is not _PRESENT and element.attrs[key] != expected:
            return False
    return True


class _TreeParser(HTMLParser):
    """void 태그를 스택에 넣지 않는 요소 트리 수집기 — `<br>`·`<input>` 같은
    태그가 형제로 `lang` 판정을 새게 하지 않는다."""

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
        if current.tag in _RAW_TEXT_TAGS:
            current.raw_text += data
        else:
            current.parts.append(data)


def _parse(resp):
    parser = _TreeParser()
    parser.feed(resp.content.decode())
    parser.close()
    return parser.root


def _get(path, lang="ko", user=None):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client.get(path, **_LANG_HEADERS[lang])


def _has_ko_ancestor(element):
    while element is not None:
        if element.attrs.get("lang") == "ko":
            return True
        element = element.parent
    return False


def _in_head(element):
    while element is not None:
        if element.tag == "head":
            return True
        element = element.parent
    return False


def _is_ko_scoped(element):
    """요소 자신·조상이 lang="ko"이거나, 요소 안의 비어 있지 않은 텍스트
    노드가 전부 lang="ko" 범위(안쪽 `<a lang="ko">` 같은 배치)면 참."""
    if _has_ko_ancestor(element):
        return True
    owners = [owner for text, owner in element.iter_text_nodes() if text.strip()]
    return bool(owners) and all(_has_ko_ancestor(owner) for owner in owners)


def _needle_langs(root, needle):
    """`<head>` 밖에서 needle을 담은 텍스트 노드마다 lang="ko" 범위 여부."""
    return [
        _has_ko_ancestor(owner)
        for text, owner in root.iter_text_nodes()
        if needle in text and not _in_head(owner)
    ]


def _one_text(root, tag=None, cls=None, attrs=None, skip=None):
    found = root.find_all(tag, cls, attrs)
    assert len(found) == 1, f"{tag}.{cls}: {len(found)}개"
    return found[0].text(skip)


def _texts(root, tag=None, cls=None, attrs=None):
    return [element.text() for element in root.find_all(tag, cls, attrs)]


def _meta_content(root, key, value):
    found = root.find_all("meta", attrs={key: value})
    assert len(found) == 1, f"meta[{key}={value}]: {len(found)}개"
    return found[0].attrs["content"]


def _title_text(root):
    return _one_text(root, "title")


_FIXED_START = date(2026, 3, 5)
_FIXED_END = date(2026, 3, 6)


def _korean_content_event(make_event, **overrides):
    fields = {
        "title": "한글 제목 행사",
        "work_title": "한글 작품명",
        "category": "popup_store",
        "region": "seoul",
        "location_name": "한글 장소",
        "summary": "한글 요약 문장",
        "source_name": "Source Site",
        "start_date": _FIXED_START,
        "end_date": _FIXED_END,
    }
    return make_event(**{**fields, **overrides})


# ---------------------------------------------------------------------------
# A. 뷰 컨텍스트와 칩
# ---------------------------------------------------------------------------

_SEARCH_CHIP = {
    "ko": "검색: poster",
    "en": "Search: poster",
    "ja": "検索: poster",
    "zh-hans": "搜索：poster",
}


# E-01
@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["ko", "en", "ja", "zh-hans"])
def test_검색어_적용_칩은_요청_언어의_번역문으로_나온다(lang):
    resp = _get("/events/?q=poster", lang)

    chips = _texts(_parse(resp), cls="applied-chip")

    assert chips == [_SEARCH_CHIP[lang]]


# E-01 포맷 문자열 주입 안전
@pytest.mark.django_db
def test_영어_검색어_칩은_퍼센트와_중괄호가_든_검색어를_그대로_보여_준다():
    resp = Client().get("/events/", {"q": "50% {할인}"}, HTTP_ACCEPT_LANGUAGE="en")

    chips = _texts(_parse(resp), cls="applied-chip")

    assert chips == ["Search: 50% {할인}"]


_FILTER_QUERY = "q=poster&region=seoul&category=popup_store&status=all"


# E-01 (칩 구조)
@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/events/", "/events/calendar/"])
def test_적용_칩은_문자열_리스트이고_카테고리는_번역_라벨이다(path):
    resp = _get(f"{path}?{_FILTER_QUERY}")

    chips = resp.context["active_filter_chips"]

    assert [str(chip) for chip in chips] == [
        "검색: poster",
        "서울",
        "팝업스토어",
        "전체",
    ]


# E-09 (lang="ko") 칩
@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/events/", "/events/calendar/"])
def test_영어에서_어떤_적용_칩도_lang_ko_범위가_아니다(path):
    resp = _get(f"{path}?{_FILTER_QUERY}", "en")

    chips = _parse(resp).find_all(cls="applied-chip")

    assert [_is_ko_scoped(chip) for chip in chips] == [False] * 4


# E-01 (뷰 컨텍스트 category_labels)
@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/events/", "/events/calendar/"])
def test_목록과_달력_컨텍스트의_category_labels는_요청_언어로_렌더된다(path):
    resp = _get(path, "en")

    assert str(resp.context["category_labels"]["popup_store"]) == "Pop-up store"


# E-02
@pytest.mark.django_db
@pytest.mark.parametrize("lang, expected", [("ko", "2026년 3월"), ("en", "March 2026")])
def test_달력_month_label은_요청_언어의_연월이다(lang, expected):
    resp = _get("/events/calendar/?month=2026-03", lang)

    assert resp.context["month_label"] == expected


# E-03
@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["ko", "en", "ja", "zh-hans"])
def test_정보가_없는_행사_상세의_기본_메타_설명은_같은_언어_홈과_같고_잘리지_않는다(
    make_event, lang
):
    event = make_event(title="Minimal Event")

    home = _parse(_get("/", lang))
    detail = _parse(_get(f"/events/{event.id}/", lang))

    home_description = _meta_content(home, "name", "description")
    detail_description = _meta_content(detail, "name", "description")
    assert detail_description == home_description
    assert not detail_description.endswith("…")
    assert _meta_content(detail, "property", "og:description") == home_description


# ---------------------------------------------------------------------------
# B. 목록
# ---------------------------------------------------------------------------

_LIST_H1 = {
    "ko": "이벤트 목록",
    "en": "Events",
    "ja": "イベント一覧",
    "zh-hans": "活动列表",
}


# E-05 (B 목록 h1·title)
@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["ko", "en", "ja", "zh-hans"])
def test_목록_h1과_title과_og_title은_요청_언어의_페이지_제목이다(lang):
    root = _parse(_get("/events/", lang))

    main = root.find_all("main", attrs={"id": "content"})[0]
    expected = _LIST_H1[lang]
    assert _texts(main, "h1") == [expected]
    assert _title_text(root) == f"{expected} — takulife"
    assert _meta_content(root, "property", "og:title") == f"{expected} — takulife"


# E-06
@pytest.mark.django_db
@pytest.mark.parametrize("lang, expected", [("ko", "3월"), ("en", "March")])
def test_목록_행의_월_표기는_요청_언어의_월_이름이다(make_event, lang, expected):
    make_event(title="Month Event", start_date=_FIXED_START, end_date=_FIXED_END)

    root = _parse(_get("/events/?status=all", lang))

    assert _texts(root, cls="event-index-month") == [expected]


# E-07
@pytest.mark.django_db
@pytest.mark.parametrize("lang, expected", [("ko", "서울, 적용됨"), ("en", "Seoul, applied")])
def test_적용된_지역_빠른_칩의_aria_label은_요청_언어의_번역문이다(lang, expected):
    root = _parse(_get("/events/?region=seoul", lang))

    active_chips = root.find_all("a", cls="chip")
    active_chips = [chip for chip in active_chips if "active" in chip.classes]
    assert [chip.attrs.get("aria-label") for chip in active_chips] == [expected]


# E-08
@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang, count, expected",
    [
        ("ko", 1, "검색 결과 1개"),
        ("ko", 2, "검색 결과 2개"),
        ("en", 1, "1 result"),
        ("en", 2, "2 results"),
        ("ja", 2, "検索結果 2件"),
        ("zh-hans", 2, "2项结果"),
    ],
)
def test_목록_결과_제목은_개수에_맞는_번역문이고_숫자는_results_count_안에_있다(
    make_event, lang, count, expected
):
    for index in range(count):
        make_event(
            title=f"Result Event {index}",
            start_date=_FIXED_START,
            end_date=_FIXED_END,
        )

    root = _parse(_get("/events/?status=all", lang))

    titles = root.find_all("h2", cls="results-title")
    assert [title.text() for title in titles] == [expected]
    counters = titles[0].find_all("span", cls="results-count")
    assert [counter.text() for counter in counters] == [str(count)]


# E-09 목록
@pytest.mark.django_db
def test_영어_목록에서_콘텐츠_필드만_lang_ko_범위다(make_event):
    _korean_content_event(make_event)

    root = _parse(_get("/events/?status=all", "en"))

    for cls, tag in (
        ("event-index-title", "h2"),
        ("event-index-work", "p"),
    ):
        elements = root.find_all(tag, cls=cls)
        assert elements, f"{tag}.{cls} 없음"
        assert all(_is_ko_scoped(element) for element in elements), cls
    categories = root.find_all("span", cls="event-index-cat")
    assert categories and not any(_is_ko_scoped(c) for c in categories)
    for needle in ("한글 제목 행사", "한글 작품명", "한글 장소"):
        langs = _needle_langs(root, needle)
        assert langs and all(langs), needle
    seoul_langs = _needle_langs(root, "Seoul")
    assert seoul_langs and not any(seoul_langs)
    status_marks = root.find_all(cls="event-index-dday")
    assert status_marks and not any(_is_ko_scoped(mark) for mark in status_marks)


# E-09 달력
@pytest.mark.django_db
def test_영어_달력_아젠다에서_콘텐츠_필드만_lang_ko_범위다(make_event):
    _korean_content_event(make_event)

    root = _parse(_get("/events/calendar/?month=2026-03&date=2026-03-05", "en"))

    for cls, tag in (
        ("agenda-title", "h3"),
        ("agenda-work", "p"),
    ):
        elements = root.find_all(tag, cls=cls)
        assert elements, f"{tag}.{cls} 없음"
        assert all(_is_ko_scoped(element) for element in elements), cls
    categories = root.find_all("span", cls="agenda-cat")
    assert categories and not any(_is_ko_scoped(c) for c in categories)
    for needle in ("한글 제목 행사", "한글 작품명", "한글 장소"):
        langs = _needle_langs(root, needle)
        assert langs and all(langs), needle
    seoul_langs = _needle_langs(root, "Seoul")
    assert seoul_langs and not any(seoul_langs)
    status_marks = root.find_all(cls="agenda-tone")
    assert status_marks and not any(_is_ko_scoped(mark) for mark in status_marks)


# E-09 상세
@pytest.mark.django_db
def test_영어_상세에서_콘텐츠_필드만_lang_ko_범위다(make_event):
    event = _korean_content_event(make_event)

    root = _parse(_get(f"/events/{event.id}/", "en"))

    for tag, cls in (
        ("h1", "event-detail-title"),
        ("p", "event-detail-work"),
        ("p", "event-detail-location-name"),
    ):
        elements = root.find_all(tag, cls=cls)
        assert len(elements) == 1, f"{tag}.{cls}: {len(elements)}개"
        assert _is_ko_scoped(elements[0]), cls
    category_label = root.find_all("span", cls="event-detail-cat-label")
    assert len(category_label) == 1 and not _is_ko_scoped(category_label[0])
    for needle in ("한글 제목 행사", "한글 작품명", "한글 장소", "한글 요약 문장"):
        langs = _needle_langs(root, needle)
        assert langs and all(langs), needle
    seoul_langs = _needle_langs(root, "Seoul")
    assert seoul_langs and not any(seoul_langs)
    status_chip = root.find_all("span", cls="event-detail-status-chip")
    assert len(status_chip) == 1 and not _is_ko_scoped(status_chip[0])


# E-09 필터 패널·빠른 칩
@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/events/", "/events/calendar/"])
def test_영어_필터_패널과_빠른_칩의_카테고리는_lang_ko_범위가_아니다(path):
    root = _parse(_get(path, "en"))

    checks = root.find_all("label", cls="filter-check")
    category_checks = [
        check for check in checks if check.find_all("input", attrs={"name": "category"})
    ]
    region_checks = [check for check in checks if check.find_all("input", attrs={"name": "region"})]
    assert category_checks and not any(_is_ko_scoped(c) for c in category_checks)
    assert region_checks and not any(_is_ko_scoped(c) for c in region_checks)

    chips = root.find_all("a", cls="chip")
    category_chips = [c for c in chips if "category=" in c.attrs.get("href", "")]
    other_chips = [c for c in chips if "category=" not in c.attrs.get("href", "")]
    assert [c.attrs["href"].rsplit("category=", 1)[-1] for c in category_chips] == [
        "popup_store",
        "collaboration_cafe",
    ]
    assert not any(_is_ko_scoped(c) for c in category_chips)
    assert other_chips and not any(_is_ko_scoped(c) for c in other_chips)


# E-10 목록·달력
@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/events/?status=all",
        "/events/calendar/?month=2026-03&date=2026-03-05",
    ],
)
@pytest.mark.parametrize("lang, expected", [("ko", "찜"), ("en", "Save")])
def test_찜_토글_버튼의_aria_label은_요청_언어의_동작_번역이다(
    make_event, make_user, path, lang, expected
):
    make_event(title="Save Event", start_date=_FIXED_START, end_date=_FIXED_END)

    root = _parse(_get(path, lang, user=make_user()))

    buttons = root.find_all("button", attrs={"data-interest-toggle": _PRESENT})
    assert [b.attrs.get("aria-label") for b in buttons] == [expected]


# E-10 상세
@pytest.mark.django_db
@pytest.mark.parametrize("lang, expected", [("ko", "찜"), ("en", "Save")])
def test_상세_찜_버튼의_가시_텍스트는_요청_언어의_동작_번역이다(make_event, lang, expected):
    event = make_event(title="Detail Save Event")

    root = _parse(_get(f"/events/{event.id}/", lang))

    buttons = root.find_all("button", attrs={"data-interest-toggle": _PRESENT})
    assert len(buttons) == 1
    glyph = lambda element: "data-interest-glyph" in element.attrs  # noqa: E731
    assert buttons[0].text(skip=glyph) == expected


_FILTER_TOGGLE = {
    "ko": ("필터 열기 ▾", "필터 닫기 ▴"),
    "en": ("Show filters ▾", "Hide filters ▴"),
    "ja": ("フィルターを開く ▾", "フィルターを閉じる ▴"),
    "zh-hans": ("展开筛选 ▾", "收起筛选 ▴"),
}


# E-10 (E JS·서버 토글 data 속성)
@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/events/", "/events/calendar/"])
@pytest.mark.parametrize("lang", ["ko", "en", "ja", "zh-hans"])
def test_필터_토글_버튼은_열기_닫기_문구를_data_속성에_싣고_초기_텍스트는_열기_문구다(path, lang):
    root = _parse(_get(path, lang))

    toggles = root.find_all("button", cls="filter-toggle")
    assert len(toggles) == 1
    open_label, close_label = _FILTER_TOGGLE[lang]
    assert toggles[0].attrs.get("data-label-open") == open_label
    assert toggles[0].attrs.get("data-label-close") == close_label
    assert toggles[0].text() == toggles[0].attrs.get("data-label-open")


# ---------------------------------------------------------------------------
# C. 달력
# ---------------------------------------------------------------------------


# E-05 (C 달력 h1·title)
@pytest.mark.django_db
@pytest.mark.parametrize("lang, expected", [("ko", "이벤트 달력"), ("en", "Event calendar")])
def test_달력_h1과_title은_요청_언어의_페이지_제목이다(lang, expected):
    root = _parse(_get("/events/calendar/?month=2026-03", lang))

    main = root.find_all("main", attrs={"id": "content"})[0]
    assert _texts(main, "h1") == [expected]
    assert _title_text(root) == f"{expected} — takulife"


# E-12
@pytest.mark.django_db
@pytest.mark.parametrize("lang, expected", [("ko", "3월"), ("en", "March")])
def test_달력_월_이름은_요청_언어의_월_이름이다(lang, expected):
    root = _parse(_get("/events/calendar/?month=2026-03", lang))

    assert _texts(root, cls="calendar-month-name") == [expected]


# E-13
@pytest.mark.django_db
@pytest.mark.parametrize("lang, expected", [("ko", "3월 5일"), ("en", "March 5")])
def test_달력_선택일_제목은_요일을_뺀_월_일이_요청_언어로_나온다(lang, expected):
    root = _parse(_get("/events/calendar/?month=2026-03&date=2026-03-05", lang))

    heads = root.find_all(cls="date-detail-head")
    assert len(heads) == 1
    headings = heads[0].find_all("h2")
    assert len(headings) == 1
    weekday = lambda element: "date-detail-weekday" in element.classes  # noqa: E731
    assert headings[0].text(skip=weekday) == expected


# E-14
@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang, count, expected",
    [
        ("ko", 1, "이벤트 1건"),
        ("ko", 2, "이벤트 2건"),
        ("en", 1, "1 event"),
        ("en", 2, "2 events"),
        ("ja", 2, "イベント2件"),
        ("zh-hans", 2, "2个活动"),
    ],
)
def test_달력_선택일_이벤트_개수는_개수에_맞는_번역문이다(make_event, lang, count, expected):
    for index in range(count):
        make_event(
            title=f"Day Event {index}",
            start_date=_FIXED_START,
            end_date=_FIXED_START,
        )

    root = _parse(_get("/events/calendar/?month=2026-03&date=2026-03-05", lang))

    assert _texts(root, cls="date-detail-count") == [expected]


# E-15
@pytest.mark.django_db
def test_영어_달력_날짜_오류_패널에는_한글이_없다():
    root = _parse(_get("/events/calendar/?month=bad", "en"))

    panels = root.find_all(cls="calendar-error-panel")
    assert len(panels) == 1
    parts = [
        panels[0].find_all("p", cls="empty-title"),
        panels[0].find_all("p", cls="empty-note"),
        panels[0].find_all("a", cls="empty-action"),
    ]
    assert all(len(found) == 1 for found in parts)
    texts = [found[0].text() for found in parts]
    assert all(texts)
    assert [_KOREAN_RE.findall(text) for text in texts] == [[], [], []]


# ---------------------------------------------------------------------------
# D. 상세
# ---------------------------------------------------------------------------


# E-20
@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang, expected",
    [
        ("ko", "공식 홈페이지 제공"),
        ("en", "Provided by 공식 홈페이지"),
        ("ja", "提供元: 공식 홈페이지"),
        ("zh-hans", "提供方：공식 홈페이지"),
    ],
)
def test_상세_부제는_출처_이름을_요청_언어_문형에_넣고_출처는_ko_범위다(make_event, lang, expected):
    event = make_event(title="Source Event", source_name="공식 홈페이지")

    root = _parse(_get(f"/events/{event.id}/", lang))

    assert _texts(root, "p", "event-detail-subtitle") == [expected]
    source_langs = _needle_langs(root, "공식 홈페이지")
    assert source_langs
    assert all(source_langs)


# E-21
@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["ko", "en"])
def test_종료된_행사_상세의_비활성_방문_예정_버튼_title은_요청_언어다(make_event, lang):
    event = make_event(title="Ended Event", start_date=_FIXED_START, end_date=_FIXED_END)

    root = _parse(_get(f"/events/{event.id}/", lang))

    buttons = root.find_all("button", cls="status-btn", attrs={"data-status": "planned"})
    assert len(buttons) == 1
    assert "disabled" in buttons[0].attrs
    title = buttons[0].attrs.get("title", "")
    if lang == "ko":
        assert title == "종료된 이벤트는 방문 예정을 설정할 수 없습니다"
    else:
        assert title
        assert _KOREAN_RE.findall(title) == []


# E-20 (D 상세 현재 상태)
@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang, expected",
    [("ko", "현재 상태: 방문 예정"), ("en", "Current status: Planned")],
)
def test_상세_현재_상태_줄은_요청_언어_문형이다(make_event, make_user, lang, expected):
    event = make_event(title="Status Event")
    user = make_user()
    UserEventStatus.objects.create(user=user, event=event, status="planned")

    root = _parse(_get(f"/events/{event.id}/", lang, user=user))

    assert _texts(root, "p", "panel-note") == [expected]


# E-09 (lang="ko") 연관 행사
@pytest.mark.django_db
def test_영어_상세의_연관_행사_항목은_콘텐츠_값만_lang_ko_범위다(make_event):
    common = {"category": "popup_store", "start_date": _FIXED_START, "end_date": _FIXED_END}
    main = make_event(title="Related Main", **common)
    make_event(
        title="연관 한글 제목", work_title="연관 작품명", location_name="연관 장소", **common
    )
    make_event(title="연관 장소없음", **common)

    root = _parse(_get(f"/events/{main.id}/", "en"))

    rows = root.find_all("a", cls="event-detail-related-row")
    assert len(rows) == 2
    title_of = lambda row: row.find_all("span", cls="event-detail-related-title")[0]  # noqa: E731
    by_title = {title_of(row).text(): row for row in rows}
    with_place, without_place = by_title["연관 한글 제목"], by_title["연관 장소없음"]
    work = with_place.find_all("span", cls="event-detail-related-work")
    assert [element.text() for element in work] == ["연관 작품명"]
    assert all(_is_ko_scoped(element) for element in work)
    assert _is_ko_scoped(title_of(with_place))
    assert without_place.find_all("span", cls="event-detail-related-work") == []

    def meta(row):
        return row.find_all("span", cls="event-detail-related-meta")[0]

    def ko_texts(row):
        return [e.text() for e in meta(row).find_all("span", attrs={"lang": "ko"})]

    assert ko_texts(with_place) == ["연관 장소"]  # 카테고리는 번역돼 ko 범위가 아니다
    assert ko_texts(without_place) == []  # 장소 미정도 ko 범위가 아니다
    assert _KOREAN_RE.findall(meta(without_place).text()) == []


# E-15 (달력 query_failed 오류 패널)
@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["ko", "en"])
def test_달력_조회_실패_오류_패널은_요청_언어다(monkeypatch, lang):
    def _raise(*args, **kwargs):
        raise RuntimeError("월 조회 실패 주입")

    monkeypatch.setattr("web.views.events.list_published_events_for_month", _raise)

    resp = _get("/events/calendar/?month=2026-03", lang)

    assert resp.context["calendar_error"] == "query_failed"
    root = _parse(resp)
    panels = root.find_all(cls="calendar-error-panel")
    assert len(panels) == 1
    parts = [
        panels[0].find_all("p", cls="empty-title"),
        panels[0].find_all("p", cls="empty-note"),
        panels[0].find_all("a", cls="empty-action"),
    ]
    assert all(len(found) == 1 for found in parts)
    texts = [found[0].text() for found in parts]
    if lang == "ko":
        assert texts == ["불러오지 못했어요", "잠시 후 다시 시도해 주세요.", "다시 시도"]
    else:
        assert all(texts)
        assert [_KOREAN_RE.findall(text) for text in texts] == [[], [], []]


# E-20 (출처 이름 HTML 이스케이프)
@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["ko", "en"])
def test_상세_부제는_출처_이름의_HTML을_이스케이프한다(make_event, lang):
    source = '<b onmouseover="x">공식</b>'
    event = make_event(title="Escape Event", source_name=source)

    resp = _get(f"/events/{event.id}/", lang)

    body = resp.content.decode()
    assert "<b onmouseover" not in body
    assert "&lt;b onmouseover=&quot;x&quot;&gt;공식&lt;/b&gt;" in body
    root = _parse(resp)
    assert root.find_all(attrs={"onmouseover": _PRESENT}) == []
    subtitle = root.find_all("p", cls="event-detail-subtitle")
    assert len(subtitle) == 1
    assert [child.tag for child in subtitle[0].iter_elements()] == ["span"]
    expected = f"Provided by {source}" if lang == "en" else f"{source} 제공"
    assert subtitle[0].text() == expected
