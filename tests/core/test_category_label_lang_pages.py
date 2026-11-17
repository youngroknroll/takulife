"""비한국어 화면에서 새 카테고리의 한글 라벨이 `lang="ko"` 범위에 드는지
화면 단위로 검증한다(트랙 59 확장 XS-19~XS-26).
"""

from datetime import date, timedelta
from html.parser import HTMLParser

from django.test import Client
from django.utils import timezone
import pytest

from archive.models import EventInterest, PersonalEntry, UserEventStatus, VisitRecord
from core.models import Category

pytestmark = [pytest.mark.web, pytest.mark.django_db]

_VOID_TAGS = frozenset(
    "br hr img input link meta source wbr area base col embed param track".split()
)
_SKIPPED_TEXT_TAGS = frozenset({"script", "style", "title"})

_LABEL = "나이트 마켓"


class _TextNodeCollector(HTMLParser):
    """텍스트 노드마다 (공백 정리한 텍스트, 조상 체인)을 모은다.

    조상 체인은 (태그, 클래스 집합, lang) 튜플의 리스트이고 `<html>`은 뺀다.
    """

    def __init__(self):
        super().__init__()
        self._stack = []
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            return
        attr_map = dict(attrs)
        classes = frozenset((attr_map.get("class") or "").split())
        self._stack.append((tag, classes, attr_map.get("lang")))

    def handle_endtag(self, tag):
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                return

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        if any(entry[0] in _SKIPPED_TEXT_TAGS for entry in self._stack):
            return
        chain = tuple(entry for entry in self._stack if entry[0] != "html")
        self.nodes.append((text, chain))


def _text_nodes(response):
    collector = _TextNodeCollector()
    collector.feed(response.content.decode())
    collector.close()
    return collector.nodes


def _is_ko_scoped(chain):
    return any(lang == "ko" for _tag, _classes, lang in chain)


def _in_class(chain, class_name):
    return any(class_name in classes for _tag, classes, _lang in chain)


def _get_english(path):
    return Client().get(path, HTTP_ACCEPT_LANGUAGE="en")


def _new_category_event(make_event):
    Category.objects.create(slug="night_market", label=_LABEL)
    return make_event(
        title="Sample Show",
        category="night_market",
        region="seoul",
        location_name="Sample Hall",
        summary="Sample summary",
        source_name="Source Site",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 6),
    )


def test_영어_행사_목록은_새_카테고리_라벨을_ko_언어_범위로_표시한다(make_event):
    _new_category_event(make_event)

    # 기본 목록은 진행 중·예정만 보여주므로 지난 행사가 나오게 status=all을 쓴다.
    nodes = _text_nodes(_get_english("/events/?status=all"))

    row_label_nodes = [
        (text, chain)
        for text, chain in nodes
        if text == _LABEL and any("event-index-cat" in classes for _tag, classes, _lang in chain)
    ]
    assert row_label_nodes
    assert [text for text, chain in row_label_nodes if not _is_ko_scoped(chain)] == []


def test_영어_행사_달력의_일정_목록은_새_카테고리_라벨을_ko_언어_범위로_표시한다(make_event):
    _new_category_event(make_event)

    nodes = _text_nodes(_get_english("/events/calendar/?month=2026-03&date=2026-03-05"))

    agenda_label_nodes = [
        (text, chain)
        for text, chain in nodes
        if text == _LABEL and any("agenda-cat" in classes for _tag, classes, _lang in chain)
    ]
    assert agenda_label_nodes
    assert [text for text, chain in agenda_label_nodes if not _is_ko_scoped(chain)] == []


def test_영어_홈_달력의_범례와_일정은_새_카테고리_라벨을_ko_언어_범위로_표시한다(make_event):
    today = timezone.localdate()
    _new_category_event(make_event)
    make_event(
        title="Today Show",
        category="night_market",
        region="seoul",
        location_name="Sample Hall",
        summary="Sample summary",
        source_name="Source Site",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=1),
    )

    nodes = _text_nodes(_get_english("/"))

    for class_name in ("legend-label", "agenda-cat"):
        label_nodes = [
            (text, chain)
            for text, chain in nodes
            if text == _LABEL and any(class_name in classes for _tag, classes, _lang in chain)
        ]
        assert label_nodes, class_name
        assert [text for text, chain in label_nodes if not _is_ko_scoped(chain)] == []


def test_영어_행사_상세는_새_카테고리_라벨을_ko_언어_범위로_표시한다(make_event):
    event = _new_category_event(make_event)
    make_event(
        title="Other Show",
        category="night_market",
        region="seoul",
        location_name="Other Hall",
        summary="Other summary",
        source_name="Source Site",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 6),
    )

    nodes = _text_nodes(_get_english(f"/events/{event.id}/"))

    positions = {
        "이동 경로 링크": lambda text, chain: _in_class(chain, "event-detail-breadcrumb"),
        "카테고리 줄": lambda text, chain: _in_class(chain, "event-detail-cat-label"),
        "정보 표": lambda text, chain: chain and chain[-1][0] == "dd",
        "관련 행사 줄": lambda text, chain: _in_class(chain, "event-detail-related-meta"),
    }
    for name, is_position in positions.items():
        label_nodes = [
            (text, chain) for text, chain in nodes if _LABEL in text and is_position(text, chain)
        ]
        assert label_nodes, name
        assert [text for text, chain in label_nodes if not _is_ko_scoped(chain)] == []


@pytest.mark.parametrize(
    "경로",
    [
        pytest.param("/events/?category=night_market&status=all", id="목록_결과있음"),
        pytest.param("/events/?category=night_market&q=zzz", id="목록_결과없음"),
        pytest.param("/events/calendar/?category=night_market&month=2026-03", id="달력"),
    ],
)
def test_영어_적용_필터_칩은_새_카테고리_라벨만_ko_언어_범위로_표시한다(make_event, 경로):
    _new_category_event(make_event)

    nodes = _text_nodes(_get_english(경로))

    chip_nodes = [(text, chain) for text, chain in nodes if _in_class(chain, "applied-chip")]
    label_chips = [(text, chain) for text, chain in chip_nodes if text == _LABEL]
    other_chips = [(text, chain) for text, chain in chip_nodes if text != _LABEL]
    assert label_chips
    assert [text for text, chain in label_chips if not _is_ko_scoped(chain)] == []
    assert [text for text, chain in other_chips if _is_ko_scoped(chain)] == []


def test_영어_방문_목록의_칩은_새_카테고리_칩에만_ko_언어_범위를_붙인다(make_event, user_client):
    user, client = user_client()
    event = _new_category_event(make_event)
    VisitRecord.objects.create(user=user, event=event, visited_on=date(2026, 3, 5))
    entry = PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="Own Place", category="내 분류"
    )
    VisitRecord.objects.create(user=user, personal_entry=entry, visited_on=date(2026, 3, 6))

    response = client.get("/archive/visits/", HTTP_ACCEPT_LANGUAGE="en")

    chips = {
        text: chain
        for text, chain in _text_nodes(response)
        if _in_class(chain, "chip") and text in (_LABEL, "내 분류")
    }
    assert set(chips) == {_LABEL, "내 분류"}
    assert _is_ko_scoped(chips[_LABEL])
    assert not _is_ko_scoped(chips["내 분류"])


def _activity_event(make_event, title, today):
    return make_event(
        title=title,
        category="night_market",
        region="seoul",
        location_name="Sample Hall",
        summary="Sample summary",
        source_name="Source Site",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=10),
    )


@pytest.mark.parametrize(
    ("경로", "라벨_클래스"),
    [
        pytest.param("/archive/", ("record-row-cat",), id="기록장"),
        pytest.param("/archive/statuses/", ("record-row-cat",), id="나의_일정"),
        pytest.param("/archive/visits/", ("record-row-cat",), id="방문_목록"),
        pytest.param("/archive/visits/{visit_id}/", ("visit-detail-cat", "dd"), id="방문_상세"),
        pytest.param("/archive/visits/{visit_id}/edit/", ("visit-chip",), id="방문_수정"),
        pytest.param("/archive/interests/", ("record-row-cat",), id="찜_목록"),
        pytest.param("/", ("snapshot-record-cat",), id="로그인_홈_기록_대기"),
    ],
)
def test_영어_활동_화면은_새_카테고리_공식_행사_라벨을_ko_언어_범위로_표시한다(
    make_event, user_client, 경로, 라벨_클래스
):
    user, client = user_client()
    today = timezone.localdate()
    _new_category_event(make_event)
    waiting = _activity_event(make_event, "Waiting Show", today)
    visited = _activity_event(make_event, "Visited Show", today)
    wished = _activity_event(make_event, "Wished Show", today)
    UserEventStatus.objects.create(user=user, event=waiting, status=UserEventStatus.Status.VISITED)
    visit = VisitRecord.objects.create(user=user, event=visited, visited_on=today)
    EventInterest.objects.create(user=user, event=wished)

    response = client.get(경로.format(visit_id=visit.id), HTTP_ACCEPT_LANGUAGE="en")

    label_nodes = [
        (text, chain)
        for text, chain in _text_nodes(response)
        if text == _LABEL
        and (
            any(_in_class(chain, name) for name in 라벨_클래스)
            or (chain and chain[-1][0] in 라벨_클래스)
        )
    ]
    assert label_nodes
    assert [text for text, chain in label_nodes if not _is_ko_scoped(chain)] == []


@pytest.mark.parametrize(
    ("경로", "라벨_위치"),
    [
        pytest.param("/events/?status=all", ("event-index-cat",), id="행사_목록_행"),
        pytest.param(
            "/events/{event_id}/",
            (
                "event-detail-breadcrumb",
                "event-detail-cat-label",
                "event-detail-related-meta",
                "dd",
            ),
            id="행사_상세",
        ),
        pytest.param("/events/?category=night_market&status=all", ("applied-chip",), id="적용_칩"),
        pytest.param("/archive/visits/", ("chip",), id="방문_칩"),
        pytest.param("/archive/visits/{visit_id}/", ("visit-detail-cat", "dd"), id="방문_상세"),
    ],
)
def test_한국어_화면에서는_새_카테고리_라벨_어디에도_lang_속성이_붙지_않는다(
    make_event, user_client, 경로, 라벨_위치
):
    user, client = user_client()
    event = _new_category_event(make_event)
    make_event(
        title="Other Show",
        category="night_market",
        region="seoul",
        location_name="Other Hall",
        summary="Other summary",
        source_name="Source Site",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 6),
    )
    visit = VisitRecord.objects.create(user=user, event=event, visited_on=date(2026, 3, 5))

    response = client.get(경로.format(event_id=event.id, visit_id=visit.id))

    label_nodes = [
        (text, chain)
        for text, chain in _text_nodes(response)
        if _LABEL in text
        and (
            any(_in_class(chain, name) for name in 라벨_위치)
            or (chain and chain[-1][0] in 라벨_위치)
        )
    ]
    assert label_nodes
    assert [text for text, chain in label_nodes if any(lang for _t, _c, lang in chain)] == []
