"""트랙 43-2: 영어 이벤트 화면(목록·달력·상세)에 `lang="ko"` 밖 한글이 없다는
합격 테스트(E-26).

`test_event_ui_translations.py`에서 분리한 파일이다(파일 800줄 이하 규칙).
`tests`에 `__init__.py`가 없어 파일 간 임포트가 불안정하므로, 요소 트리
파서와 요청 헬퍼는 그 파일에서 복제했다. `.mo`가 로컬에 컴파일돼 있어야 한다
(`uv run django-admin compilemessages --ignore .venv`).
"""

import re
from datetime import date, timedelta
from html.parser import HTMLParser

import pytest
from django.test import Client
from django.utils import timezone

from archive.models import EventInterest, UserEventStatus

pytestmark = pytest.mark.web

_KOREAN_RE = re.compile(r"[가-힣]")
_BRAND_NAME = "타쿠라이프"

_LANG_HEADERS = {"en": {"HTTP_ACCEPT_LANGUAGE": "en"}}

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


_FIXED_START = date(2026, 3, 5)
_FIXED_END = date(2026, 3, 6)


# ---------------------------------------------------------------------------
# 영어 화면 한글 누수 스캔
# ---------------------------------------------------------------------------

_SCAN_ATTRS = ("aria-label", "title", "placeholder", "alt")
_SCAN_TITLE = "스캔 제목"


def _scan_list_filtered(make_event, make_user):
    user = make_user()
    today = timezone.localdate()
    common = {
        "category": "popup_store",
        "region": "seoul",
        "work_title": "Scan Work",
        "location_name": "Scan Hall",
    }
    ended = make_event(
        title="Scan Event Ended",
        start_date=_FIXED_START,
        end_date=_FIXED_END,
        official_url="https://example.com/scan-ended",
        **common,
    )
    make_event(
        title="Scan Event Upcoming",
        start_date=today + timedelta(days=3),
        end_date=today + timedelta(days=10),
        **common,
    )
    closing = make_event(
        title="Scan Event Closing",
        start_date=today - timedelta(days=3),
        end_date=today + timedelta(days=1),
        **common,
    )
    make_event(
        title="Scan Event Today",
        start_date=today - timedelta(days=3),
        end_date=today,
        **common,
    )
    make_event(title="Scan Event Undated", **common)
    UserEventStatus.objects.create(user=user, event=ended, status="visited")
    EventInterest.objects.create(user=user, event=closing)
    path = "/events/?q=Scan&region=seoul&category=popup_store&status=all"
    return user, path, []


def _scan_list_empty_query(make_event, make_user):
    return None, "/events/?q=zzqq", []


def _scan_list_empty_default(make_event, make_user):
    return None, "/events/", []


def _calendar_day_events(make_event):
    common = {"category": "popup_store", "region": "seoul", "location_name": "Scan Hall"}
    single = make_event(
        title="Scan Day Event",
        work_title="Scan Work",
        start_date=_FIXED_START,
        end_date=_FIXED_START,
        **common,
    )
    make_event(
        title="Scan Range Event",
        start_date=_FIXED_START,
        end_date=_FIXED_START + timedelta(days=2),
        **common,
    )
    make_event(title="Scan Place-less Event", start_date=_FIXED_START, end_date=_FIXED_START)
    return single


_CALENDAR_DAY = "/events/calendar/?month=2026-03&date=2026-03-05&q=Scan"


def _scan_calendar_anonymous(make_event, make_user):
    _calendar_day_events(make_event)
    return None, _CALENDAR_DAY, []


def _scan_calendar_logged_in(make_event, make_user):
    user = make_user()
    single = _calendar_day_events(make_event)
    EventInterest.objects.create(user=user, event=single)
    UserEventStatus.objects.create(user=user, event=single, status="visited")
    return user, _CALENDAR_DAY, []


def _scan_calendar_error(make_event, make_user):
    return None, "/events/calendar/?month=bad", []


def _scan_calendar_empty_day(make_event, make_user):
    _calendar_day_events(make_event)
    return None, "/events/calendar/?month=2026-03&date=2026-03-10", []


def _scan_detail_logged_in(make_event, make_user):
    user = make_user()
    event = make_event(
        title=_SCAN_TITLE,
        work_title="Scan Work",
        location_name="Scan Hall",
        region="seoul",
        source_name="공식 홈페이지",
        official_url="https://example.com/scan-detail",
        start_date=_FIXED_START,
        end_date=_FIXED_END,
    )
    UserEventStatus.objects.create(user=user, event=event, status="planned")
    EventInterest.objects.create(user=user, event=event)
    return user, f"/events/{event.id}/", [_SCAN_TITLE]


def _scan_detail_visited(make_event, make_user):
    user = make_user()
    event = make_event(
        title="Scan Visited Event",
        location_name="Scan Hall",
        official_url="https://example.com/scan-visited",
        start_date=_FIXED_START,
        end_date=_FIXED_END,
    )
    UserEventStatus.objects.create(user=user, event=event, status="visited")
    return user, f"/events/{event.id}/", []


def _scan_detail_ended(make_event, make_user):
    event = make_event(title="Scan Ended Event", start_date=_FIXED_START, end_date=_FIXED_END)
    return None, f"/events/{event.id}/", []


def _scan_detail_minimal(make_event, make_user):
    event = make_event(title="Scan Minimal Event")
    return None, f"/events/{event.id}/", []


def _scan_detail_related(make_event, make_user):
    common = {
        "category": "popup_store",
        "region": "seoul",
        "location_name": "Scan Hall",
        "start_date": _FIXED_START,
        "end_date": _FIXED_END,
    }
    event = make_event(title="Scan Related Main", work_title="Scan Work", **common)
    make_event(title="Scan Related One", work_title="Scan Work One", **common)
    make_event(title="Scan Related Two", **{**common, "location_name": ""})
    return None, f"/events/{event.id}/", []


_ALL_CATEGORIES = (
    "popup_store",
    "collaboration_cafe",
    "theater_bonus",
    "goods_reservation",
    "exhibition",
    "fan_meeting",
    "concert",
)


def _scan_list_all_categories(make_event, make_user):
    for slug in _ALL_CATEGORIES:
        make_event(
            title=f"Scan Cat {slug}",
            category=slug,
            region="seoul",
            location_name="Scan Hall",
            start_date=_FIXED_START,
            end_date=_FIXED_END,
        )
    return None, "/events/?status=all", []


def _scan_calendar_all_categories(make_event, make_user):
    for slug in _ALL_CATEGORIES:
        make_event(
            title=f"Scan Cat {slug}",
            category=slug,
            region="seoul",
            location_name="Scan Hall",
            start_date=_FIXED_START,
            end_date=_FIXED_START,
        )
    return None, "/events/calendar/?month=2026-03&date=2026-03-05", []


_SCANS = {
    "list_filtered": _scan_list_filtered,
    "list_empty_query": _scan_list_empty_query,
    "list_empty_default": _scan_list_empty_default,
    "calendar_anonymous": _scan_calendar_anonymous,
    "calendar_logged_in": _scan_calendar_logged_in,
    "calendar_error": _scan_calendar_error,
    "calendar_empty_day": _scan_calendar_empty_day,
    "detail_logged_in": _scan_detail_logged_in,
    "detail_visited": _scan_detail_visited,
    "detail_ended": _scan_detail_ended,
    "detail_minimal": _scan_detail_minimal,
    "detail_related": _scan_detail_related,
    "list_all_categories": _scan_list_all_categories,
    "calendar_all_categories": _scan_calendar_all_categories,
}


def _without_allowed(text, allowed):
    text = text.replace(_BRAND_NAME, "")
    for allowed_text in allowed:
        text = text.replace(str(allowed_text), "")
    return text


def _korean_leaks(root, scene, allowed_content):
    leaks = []
    for text, owner in root.iter_text_nodes():
        if _has_ko_ancestor(owner):
            continue
        allowed = allowed_content if owner.tag == "title" else []
        cleaned = _without_allowed(text, allowed)
        if _KOREAN_RE.search(cleaned):
            leaks.append(f"{scene}:<{owner.tag}>:{cleaned.strip()[:40]!r}")
    for element in root.iter_elements():
        if _has_ko_ancestor(element):
            continue
        names = list(_SCAN_ATTRS)
        if element.tag == "meta":
            names.append("content")
        for name in names:
            value = element.attrs.get(name)
            if not value:
                continue
            allowed = allowed_content if element.tag == "meta" else []
            cleaned = _without_allowed(value, allowed)
            if _KOREAN_RE.search(cleaned):
                leaks.append(f"{scene}:<{element.tag} {name}>:{cleaned.strip()[:40]!r}")
    return leaks


# E-26
@pytest.mark.django_db
@pytest.mark.parametrize("scene", list(_SCANS))
def test_영어_이벤트_화면에는_lang_ko_밖의_한글이_없다(make_event, make_user, scene):
    user, path, allowed_content = _SCANS[scene](make_event, make_user)

    resp = _get(path, "en", user=user)

    assert resp.status_code == 200
    assert _korean_leaks(_parse(resp), scene, allowed_content) == []


# E-26 (거짓 통과 방지: detail_related 장면은 연관 행사 섹션이 실제로 그려진다)
@pytest.mark.django_db
def test_detail_related_장면은_영어_연관_행사_섹션과_항목_2개를_그린다(make_event, make_user):
    user, path, _ = _scan_detail_related(make_event, make_user)

    root = _parse(_get(path, "en", user=user))

    sections = root.find_all("section", cls="event-detail-related")
    assert len(sections) == 1
    heads = sections[0].find_all("h2")
    assert len(heads) == 1
    title = heads[0].text()
    assert title and title != "이런 행사도 있어요"
    assert _KOREAN_RE.findall(title) == []
    assert len(sections[0].find_all("a", cls="event-detail-related-row")) == 2
