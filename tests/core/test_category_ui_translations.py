"""트랙 43-2: 카테고리 이름 번역 계약.

카테고리 이름이 렌더되는 모든 자리(목록 행·적용 칩·빠른 칩·필터 체크박스·
상세·달력 아젠다·홈 타일·메타 설명·방문 기록 칩)가 요청 언어의 번역을 쓰고,
번역된 텍스트에는 `lang="ko"`가 붙지 않는다. DB에만 있고 번역이 없는
한국어 라벨만 `lang="ko"`를 유지한다. 단언은 HTML을 파싱해 요소 단위 등식으로
하고 부분 문자열 비교는 쓰지 않는다.
"""

from datetime import date
from html.parser import HTMLParser
import json
import re
from unittest.mock import patch

from django.test import Client
import pytest

from archive.models import PersonalEntry, UserEventStatus
from core.models import Category, HomeConfig

pytestmark = pytest.mark.web

_KOREAN_RE = re.compile(r"[가-힣]")

_LANG_HEADERS = {
    "ko": {},
    "en": {"HTTP_ACCEPT_LANGUAGE": "en"},
    "ja": {"HTTP_ACCEPT_LANGUAGE": "ja"},
    "zh-hans": {"HTTP_ACCEPT_LANGUAGE": "zh-hans"},
}

_SOURCE = {
    "popup_store": "팝업스토어",
    "collaboration_cafe": "콜라보 카페",
    "theater_bonus": "극장 특전",
    "goods_reservation": "굿즈 예약",
    "exhibition": "전시",
    "fan_meeting": "팬미팅",
    "concert": "콘서트",
}

# 계획서 §2-14의 고정 번역표 — 구현이 바뀌어도 이 표가 기대값이다.
_TRANSLATED = {
    "ko": _SOURCE,
    "en": {
        "popup_store": "Pop-up store",
        "collaboration_cafe": "Collab café",
        "theater_bonus": "Theater bonus",
        "goods_reservation": "Goods pre-order",
        "exhibition": "Exhibition",
        "fan_meeting": "Fan meeting",
        "concert": "Concert",
    },
    "ja": {
        "popup_store": "ポップアップストア",
        "collaboration_cafe": "コラボカフェ",
        "theater_bonus": "劇場特典",
        "goods_reservation": "グッズ予約",
        "exhibition": "展示",
        "fan_meeting": "ファンミーティング",
        "concert": "コンサート",
    },
    "zh-hans": {
        "popup_store": "快闪店",
        "collaboration_cafe": "联动咖啡厅",
        "theater_bonus": "影院特典",
        "goods_reservation": "周边预订",
        "exhibition": "展览",
        "fan_meeting": "粉丝见面会",
        "concert": "演唱会",
    },
}

_FOREIGN_LANGS = ["en", "ja", "zh-hans"]
_ALL_LANGS = ["ko", "en", "ja", "zh-hans"]
_SLUGS = list(_SOURCE)

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
        self.parts = []
        self.raw_text = ""

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()

    def text(self):
        pieces = []
        for part in self.parts:
            pieces.append(part if isinstance(part, str) else part.text())
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


def _is_ko_scoped(element):
    """요소 자신·조상이 lang="ko"이거나, 요소 안의 비어 있지 않은 텍스트
    노드가 전부 lang="ko" 범위면 참."""
    if _has_ko_ancestor(element):
        return True
    owners = [owner for text, owner in element.iter_text_nodes() if text.strip()]
    return bool(owners) and all(_has_ko_ancestor(owner) for owner in owners)


def _not_ko_marked(lang, element):
    """번역된 카테고리 요소에 `lang="ko"` 표시가 없는지. 한국어 요청은 문서 루트가
    `<html lang="ko">`라 범위 판정이 항상 참이므로, 요소와 `<html>`을 뺀 조상에
    명시적 `lang` 속성이 전혀 없는지로 확인한다."""
    if lang != "ko":
        return not _is_ko_scoped(element)
    while element is not None and element.tag != "html":
        if "lang" in element.attrs:
            return False
        element = element.parent
    return True


def _meta_content(root, key, value):
    found = root.find_all("meta", attrs={key: value})
    assert len(found) == 1, f"meta[{key}={value}]: {len(found)}개"
    return found[0].attrs["content"]


_START = date(2026, 3, 5)
_END = date(2026, 3, 6)


def _event(make_event, category, **overrides):
    fields = {
        "title": f"행사 {category}",
        "category": category,
        "region": "seoul",
        "location_name": "한글 장소",
        "summary": "한글 요약 문장",
        "source_name": "Source Site",
        "start_date": _START,
        "end_date": _END,
    }
    return make_event(**{**fields, **overrides})


def _checkbox_labels(root):
    """카테고리 체크박스 라벨 요소 목록(slug → label 요소)."""
    labels = {}
    for label in root.find_all("label", "filter-check"):
        inputs = label.find_all("input", attrs={"name": "category"})
        if inputs:
            labels[inputs[0].attrs["value"]] = label
    return labels


# ---------------------------------------------------------------------------
# C-02 적용 칩
# ---------------------------------------------------------------------------


# C-02 — Red 예측: en·ja·zh는 지금 한국어 칩(+lang="ko")이라 Red, ko는 Green.
@pytest.mark.django_db
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_카테고리_적용_칩은_요청_언어의_번역_라벨이다(lang):
    root = _parse(_get("/events/?category=popup_store", lang))

    chips = root.find_all(cls="applied-chip")

    assert [chip.text() for chip in chips] == [_TRANSLATED[lang]["popup_store"]]
    assert [_not_ko_marked(lang, chip) for chip in chips] == [True]


# ---------------------------------------------------------------------------
# C-03 목록 행
# ---------------------------------------------------------------------------


# C-03 — Red 예측: 외국어 21개는 한국어 행 라벨이라 Red, ko 7개는 Green.
@pytest.mark.django_db
@pytest.mark.parametrize("lang", _ALL_LANGS)
@pytest.mark.parametrize("slug", _SLUGS)
def test_목록_행의_카테고리는_고정_번역표와_같다(make_event, lang, slug):
    for category in _SLUGS:
        _event(make_event, category)

    root = _parse(_get("/events/?status=all", lang))

    rows = {}
    for main in root.find_all(cls="event-index-main"):
        title = main.find_all("h2", "event-index-title")[0].text()
        rows[title] = main.find_all(cls="event-index-cat")
    cat = rows[f"행사 {slug}"]
    assert [element.text() for element in cat] == [_TRANSLATED[lang][slug]]
    assert [_not_ko_marked(lang, element) for element in cat] == [True]


# ---------------------------------------------------------------------------
# C-04 상세와 달력 아젠다
# ---------------------------------------------------------------------------


# C-04 — Red 예측: 지금은 세 자리 모두 한국어+lang="ko"라 Red.
@pytest.mark.django_db
def test_영어_상세의_카테고리_줄_세_곳은_번역_라벨이고_ko_범위가_아니다(make_event):
    event = _event(make_event, "popup_store")

    root = _parse(_get(f"/events/{event.id}/", "en"))

    breadcrumb = root.find_all("a", attrs={"href": "/events/?category=popup_store"})
    label = root.find_all(cls="event-detail-cat-label")
    info_rows = [
        row
        for row in root.find_all(cls="event-detail-meta-row")
        if [dt.text() for dt in row.find_all("dt")] == ["Category"]
    ]
    assert len(info_rows) == 1
    info = info_rows[0].find_all("dd")
    elements = breadcrumb + label + info
    assert [element.text() for element in elements] == ["Pop-up store"] * 3
    assert [_is_ko_scoped(element) for element in elements] == [False] * 3


# C-04 (달력 아젠다) — Red 예측: 지금은 한국어+lang="ko"라 Red.
@pytest.mark.django_db
def test_영어_달력_아젠다의_카테고리는_번역_라벨이고_ko_범위가_아니다(make_event):
    _event(make_event, "popup_store")

    root = _parse(_get("/events/calendar/?month=2026-03&date=2026-03-05", "en"))

    cats = root.find_all(cls="agenda-cat")
    assert [cat.text() for cat in cats] == ["Pop-up store"]
    assert [_is_ko_scoped(cat) for cat in cats] == [False]


# ---------------------------------------------------------------------------
# C-06 빠른 칩
# ---------------------------------------------------------------------------


def _quick_category_chips(root):
    return [
        chip
        for chip in root.find_all("a", "chip")
        if chip.attrs.get("href", "").startswith("/events/?category=")
    ]


# C-06 — Red 예측: 지금은 한국어+lang="ko"라 Red.
@pytest.mark.django_db
def test_영어_빠른_칩_두_개는_번역_라벨이고_ko_범위가_아니다():
    chips = _quick_category_chips(_parse(_get("/events/", "en")))

    assert [chip.attrs["href"] for chip in chips] == [
        "/events/?category=popup_store",
        "/events/?category=collaboration_cafe",
    ]
    assert [chip.text() for chip in chips] == ["Pop-up store", "Collab café"]
    assert [_is_ko_scoped(chip) for chip in chips] == [False, False]


# C-06 (aria-label) — Red 예측: 지금은 aria-label이 한국어 라벨이라 Red.
@pytest.mark.django_db
def test_카테고리가_적용된_영어_요청에서_빠른_칩의_aria_label은_칩_텍스트로_시작한다():
    root = _parse(_get("/events/?category=popup_store", "en"))

    chip = _quick_category_chips(root)[0]

    assert chip.text() == "Pop-up store"
    assert chip.attrs["aria-label"].startswith(chip.text())
    assert chip.attrs["aria-label"] != chip.text()


# ---------------------------------------------------------------------------
# C-08 필터 체크박스
# ---------------------------------------------------------------------------


# C-08 — Red 예측: 외국어 6개(목록·달력 × 3개 언어)는 한국어+lang="ko"라 Red,
# ko 2개는 Green.
@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/events/", "/events/calendar/"])
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_필터_체크박스_라벨은_고정_번역표와_같고_번역된_라벨은_ko_범위가_아니다(path, lang):
    labels = _checkbox_labels(_parse(_get(path, lang)))

    assert {slug: labels[slug].text() for slug in _SLUGS} == _TRANSLATED[lang]
    assert [_not_ko_marked(lang, labels[slug]) for slug in _SLUGS] == [True] * 7
    if lang == "ko":
        assert [("lang" in labels[slug].attrs) for slug in _SLUGS] == [False] * 7


# ---------------------------------------------------------------------------
# C-09 번역 없는 DB 라벨
# ---------------------------------------------------------------------------


@pytest.fixture
def untranslated_categories(db):
    Category.objects.create(slug="zz_night_market", label="야시장", sort_order=900)
    Category.objects.create(slug="zz_night_en", label="Night Market", sort_order=901)


# C-09 — Red 예측: 영어에서 두 라벨 모두 지금은 lang="ko" 범위라 Red
# (Night Market이 ko 범위로 잡힌다). ko 요청 단언은 현재도 lang이 붙어 있어 Red.
@pytest.mark.django_db
def test_영어_체크박스에서_번역_없는_한글_라벨만_ko_범위다(untranslated_categories):
    labels = _checkbox_labels(_parse(_get("/events/", "en")))

    assert labels["zz_night_market"].text() == "야시장"
    assert labels["zz_night_en"].text() == "Night Market"
    assert _is_ko_scoped(labels["zz_night_market"]) is True
    assert _is_ko_scoped(labels["zz_night_en"]) is False


# C-09 (ko) — Red 예측: 지금은 모든 체크박스에 lang="ko"라 Red.
@pytest.mark.django_db
def test_한국어_요청에서는_번역_없는_라벨_체크박스에도_lang_속성이_없다(
    untranslated_categories,
):
    labels = _checkbox_labels(_parse(_get("/events/", "ko")))

    assert labels["zz_night_market"].text() == "야시장"
    assert labels["zz_night_en"].text() == "Night Market"
    assert [("lang" in labels[s].attrs) for s in ("zz_night_market", "zz_night_en")] == [
        False,
        False,
    ]


# ---------------------------------------------------------------------------
# C-10 홈 타일
# ---------------------------------------------------------------------------


def _tile_names(root):
    return {
        tile.attrs["href"].split("=", 1)[1]: tile.find_all(cls="cat-name")[0]
        for tile in root.find_all("a", "cat-dot")
    }


def _feature_all_categories():
    config = HomeConfig.get_solo()
    config.featured_categories = [*_SLUGS, "zz_night_market"]
    config.save()


# C-10 — Red 예측: 외국어 3개는 지금 한국어+lang="ko"라 Red, ko는 lang이 붙어
# 있어 Red.
@pytest.mark.django_db
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_홈_카테고리_타일은_고정_번역표와_같고_번역된_타일은_ko_범위가_아니다(
    untranslated_categories, lang
):
    _feature_all_categories()

    names = _tile_names(_parse(_get("/", lang)))

    assert {slug: names[slug].text() for slug in _SLUGS} == _TRANSLATED[lang]
    assert [_not_ko_marked(lang, names[slug]) for slug in _SLUGS] == [True] * 7
    if lang == "ko":
        assert "lang" not in names["zz_night_market"].attrs


# C-10 (번역 없는 라벨) — Red 예측: 영어에서 타일 텍스트는 이미 야시장이고
# ko 범위도 이미 참이라 Green으로 도착할 수 있다(변이 계획 대상).
@pytest.mark.django_db
@pytest.mark.parametrize("lang", _FOREIGN_LANGS)
def test_번역_없는_DB_라벨_타일은_한국어_그대로이고_ko_범위다(untranslated_categories, lang):
    _feature_all_categories()

    names = _tile_names(_parse(_get("/", lang)))

    assert names["zz_night_market"].text() == "야시장"
    assert _is_ko_scoped(names["zz_night_market"]) is True


# ---------------------------------------------------------------------------
# C-11 메타 설명 폴백
# ---------------------------------------------------------------------------


# C-11 — Red 예측: 지금은 한국어 라벨이라 Red(200은 Green).
@pytest.mark.django_db
def test_카테고리만_있는_행사의_영어_상세는_번역_라벨로_시작하는_메타_설명을_가진다(
    make_event,
):
    event = make_event(title="카테고리만 있는 행사", category="popup_store")

    resp = _get(f"/events/{event.id}/", "en")

    assert resp.status_code == 200
    root = _parse(resp)
    description = _meta_content(root, "name", "description")
    assert description.split(" · ")[0] == "Pop-up store"
    assert _KOREAN_RE.search(description) is None
    assert _meta_content(root, "property", "og:description") == description
    # 이 행사는 시작일·위치가 없어 JSON-LD가 생략되므로 아래 루프는 돌지 않는다(공허).
    # 실제 JSON-LD 일치는 바로 아래 별도 테스트가 확인한다.
    for script in root.find_all("script", attrs={"type": "application/ld+json"}):
        payload = json.loads(script.raw_text)
        if isinstance(payload, dict) and "description" in payload:
            assert payload["description"] == description


# C-11 (JSON-LD) — Green 도착 예상. 변이: 메타 설명 폴백의 `str()` 감싸기를 지우거나
# JSON-LD `description` 전달을 `event.summary`로 되돌리면 Red.
@pytest.mark.django_db
def test_위치와_시작일이_있는_영어_상세는_JSON_LD_description이_메타_설명과_같다(make_event):
    event = make_event(
        title="JSON-LD 행사",
        category="popup_store",
        location_name="Scan Hall",
        start_date=_START,
        end_date=_END,
    )

    root = _parse(_get(f"/events/{event.id}/", "en"))

    scripts = root.find_all("script", attrs={"type": "application/ld+json"})
    assert len(scripts) == 1
    description = json.loads(scripts[0].raw_text)["description"]
    assert description == _meta_content(root, "name", "description")
    assert description.split(" · ")[0] == "Pop-up store"
    assert _KOREAN_RE.search(description) is None


# ---------------------------------------------------------------------------
# G1 홈 달력 범례·아젠다, 홈 컬렉션 스냅샷
# ---------------------------------------------------------------------------

_TODAY = date(2026, 9, 16)


# 변이: `_home_event_calendar.html`의 `.legend-label`·`.agenda-cat`에 `lang="ko"`를
# 다시 넣으면 en은 ko 범위가 되어 Red, 라벨 출력을 원문 상수로 되돌리면 en이 Red.
@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["ko", "en"])
def test_홈_달력_범례와_아젠다의_카테고리는_번역_라벨이고_ko_표시가_없다(make_event, lang):
    make_event(
        title="오늘 행사",
        category="popup_store",
        start_date=_TODAY,
        end_date=_TODAY,
    )

    with patch("web.views.events.timezone.localdate", return_value=_TODAY):
        root = _parse(_get("/", lang))

    legend = root.find_all("span", "legend-label")
    agenda = root.find_all("span", "agenda-cat")
    expected = _TRANSLATED[lang]["popup_store"]
    assert [el.text() for el in legend] == [expected]
    assert [el.text() for el in agenda] == [expected]
    assert [_not_ko_marked(lang, el) for el in legend + agenda] == [True, True]


# 변이: `_home_collection_snapshot.html`의 `.snapshot-record-cat`에 `lang="ko"`를
# 다시 넣으면 공식 행(en)이 Red, 개인 행에 `lang`을 붙이는 구현이면 개인 행 단언이 Red.
@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["ko", "en"])
def test_홈_컬렉션_스냅샷의_공식_행은_번역되고_어휘_밖_개인_입력_카테고리는_원문_그대로다(
    make_user, make_event, lang
):
    user = make_user()
    event = make_event(title="공식 방문 행사", category="popup_store")
    UserEventStatus.objects.create(user=user, event=event, status=UserEventStatus.Status.VISITED)
    # 43-3부터 제안 칩 어휘와 같은 저장값은 요청 언어로 보이므로, 번역하지 않는
    # 사용자 자유 입력은 어휘 밖 값으로 고정한다.
    entry = PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="개인 방문 장소", category="내 분류"
    )
    UserEventStatus.objects.create(
        user=user, personal_entry=entry, status=UserEventStatus.Status.VISITED
    )

    root = _parse(_get("/", lang, user=user))

    cats = {}
    for row in root.find_all("li", "snapshot-record-row"):
        title = row.find_all("p", "snapshot-record-title")[0].text()
        cats[title] = row.find_all("p", "snapshot-record-cat")
    official = cats["공식 방문 행사"]
    personal = cats["개인 방문 장소"]
    assert [el.text() for el in official] == [_TRANSLATED[lang]["popup_store"]]
    assert [_not_ko_marked(lang, el) for el in official] == [True]
    assert [el.text() for el in personal] == ["내 분류"]
    assert [_not_ko_marked("ko", el) for el in personal] == [True]


# 43-3 사용자 결정: 저장값이 제안 칩 어휘(한국어 원문)와 같으면 요청 언어로 보인다.
@pytest.mark.django_db
@pytest.mark.parametrize("lang, expected", [("ko", "팝업스토어"), ("en", "Pop-up store")])
def test_홈_컬렉션_스냅샷의_개인_카테고리가_제안_칩_어휘이면_요청_언어로_보인다(
    make_user, lang, expected
):
    user = make_user()
    entry = PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="개인 방문 장소", category="팝업스토어"
    )
    UserEventStatus.objects.create(
        user=user, personal_entry=entry, status=UserEventStatus.Status.VISITED
    )

    root = _parse(_get("/", lang, user=user))

    rows = root.find_all("li", "snapshot-record-row")
    cats = [el.text() for row in rows for el in row.find_all("p", "snapshot-record-cat")]
    assert cats == [expected]
