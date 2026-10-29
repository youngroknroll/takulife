"""트랙 43-3: 활동 달력의 월 제목과 항목 날짜 문구 번역 계약.

`month_label`은 Django 로케일의 `YEAR_MONTH_FORMAT`을 따르고(ko `2026년 3월`,
en `March 2026`), 선택일 항목의 `date_text`("7월 19일 14:32" 형태)는 한국어에서
현재 출력과 글자 단위로 같고 그 밖의 언어에서는 한글이 없다.
"""

import re
from datetime import date, datetime
from html.parser import HTMLParser

import pytest
from django.test import Client
from django.utils import timezone

from archive.models import ActivityLogEntry, CollectionItem, UserEventStatus

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


def _get(user, params, lang):
    client = Client()
    client.force_login(user)
    return client.get("/archive/calendar/", params, **_LANG_HEADERS[lang])


def _date_texts(resp):
    return [item["date_text"] for item in resp.context["selected_items"]]


def _rendered_date_texts(resp):
    return [el.text() for el in _parse(resp).find_all("span", "calendar-item-date")]


# 값은 uv run python으로 Django 로케일 YEAR_MONTH_FORMAT을 실제 출력해 확인했다.
_MONTH_LABEL = {
    "ko": "2026년 3월",
    "en": "March 2026",
    "ja": "2026年3月",
    "zh-hans": "2026年3月",
}


# Red 예측: en은 "2026년 3월"이라 Red, ko·ja·zh-hans는 현재 출력과 같아 Green 핀.
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_월_제목은_요청_언어의_연월_서식이다(user_client, lang):
    user, _ = user_client()

    resp = _get(user, {"month": "2026-03", "date": "2026-03-15"}, lang)

    assert resp.context["month_label"] == _MONTH_LABEL[lang]


def test_한국어_시각이_있는_항목의_날짜_문구는_월_일_시각_형태_그대로다(user_client):
    user, _ = user_client()
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.INTEREST_ADDED,
        occurred_at=timezone.make_aware(datetime(2026, 7, 10, 10, 0)),
        subject_label="Interest target",
    )

    resp = _get(user, {"month": "2026-07", "date": "2026-07-10"}, "ko")

    assert _date_texts(resp) == ["7월 10일 10:00"]
    assert _rendered_date_texts(resp) == ["7월 10일 10:00"]


def test_한국어_날짜만_있는_항목의_날짜_문구는_월_일_형태_그대로다(user_client):
    user, _ = user_client()
    CollectionItem.objects.create(user=user, name="Goods acquired", acquired_on=date(2026, 7, 12))

    resp = _get(user, {"month": "2026-07", "date": "2026-07-12"}, "ko")

    assert _date_texts(resp) == ["7월 12일"]
    assert _rendered_date_texts(resp) == ["7월 12일"]


def test_한국어_기간_항목의_날짜_문구는_물결표로_이은_월_일_형태_그대로다(user_client, make_event):
    user, _ = user_client()
    event = make_event(
        title="Schedule event", start_date=date(2026, 7, 10), end_date=date(2026, 7, 12)
    )
    UserEventStatus.objects.create(user=user, event=event, status=UserEventStatus.Status.PLANNED)

    resp = _get(user, {"month": "2026-07", "date": "2026-07-11"}, "ko")

    assert _date_texts(resp) == ["7월 10일~7월 12일"]
    assert _rendered_date_texts(resp) == ["7월 10일~7월 12일"]


# Red 예측: 세 언어 모두 지금은 "7월 10일 10:00"이라 Red.
@pytest.mark.parametrize("lang", _FOREIGN_LANGS)
def test_외국어_시각이_있는_항목의_날짜_문구에는_한글이_없고_시각이_남는다(user_client, lang):
    user, _ = user_client()
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.INTEREST_ADDED,
        occurred_at=timezone.make_aware(datetime(2026, 7, 10, 10, 0)),
        subject_label="Interest target",
    )

    resp = _get(user, {"month": "2026-07", "date": "2026-07-10"}, lang)

    texts = _date_texts(resp)
    assert len(texts) == 1
    assert "10:00" in texts[0]
    assert [t for t in texts + _rendered_date_texts(resp) if _KOREAN_RE.search(t)] == []


@pytest.mark.parametrize("lang", _FOREIGN_LANGS)
def test_외국어_날짜만_있는_항목의_날짜_문구에는_한글이_없다(user_client, lang):
    user, _ = user_client()
    CollectionItem.objects.create(user=user, name="Goods acquired", acquired_on=date(2026, 7, 12))

    resp = _get(user, {"month": "2026-07", "date": "2026-07-12"}, lang)

    texts = _date_texts(resp)
    assert len(texts) == 1
    assert [t for t in texts + _rendered_date_texts(resp) if _KOREAN_RE.search(t)] == []


@pytest.mark.parametrize("lang", _FOREIGN_LANGS)
def test_외국어_기간_항목의_날짜_문구에는_한글이_없고_물결표로_이어진다(
    user_client, make_event, lang
):
    user, _ = user_client()
    event = make_event(
        title="Schedule event", start_date=date(2026, 7, 10), end_date=date(2026, 7, 12)
    )
    UserEventStatus.objects.create(user=user, event=event, status=UserEventStatus.Status.PLANNED)

    resp = _get(user, {"month": "2026-07", "date": "2026-07-11"}, lang)

    texts = _date_texts(resp)
    assert len(texts) == 1
    assert "~" in texts[0]
    assert [t for t in texts + _rendered_date_texts(resp) if _KOREAN_RE.search(t)] == []
