"""트랙 43-3: 영어(·일본어·중국어) 활동 달력 화면에 `lang="ko"` 밖 한글이 없다는
합격 테스트(AC3). 나머지 아카이브·컬렉션·마이페이지 장면은 `test_archive_ui_leak_scan.py`.

판정 방식·허용 규칙은 그 파일 docstring과 같다(장면 함수가 `(user, path, allowed)`를
돌려주고, 사용자 입력은 ASCII 픽스처, 한글 사용자 입력은 `allowed`로 그 문자열만 지운다).
`tests`에 `__init__.py`가 없어 요소 트리 파서와 요청 헬퍼는 복제했다.

못 잡는 곳: 서버 렌더 밖(JS 문구)과 `value=`·`data-*` 속성(일부 제외). 활동 달력의 항목
라벨(행사 제목·굿즈 이름·방문 대상)은 출처 플래그가 없어 `lang="ko"`를 붙이지 못하는
알려진 한계라(prompt_plan 43-3 §2-10), 이 파일에는 공식 한글 제목 장면이 없다 — 라벨은
ASCII 픽스처로만 검사한다.
`.mo`가 로컬에 컴파일돼 있어야 한다(`uv run django-admin compilemessages --ignore .venv`).
"""

from datetime import datetime, timedelta
from html.parser import HTMLParser
import re

from django.test import Client
from django.utils import timezone
import pytest

from archive.models import (
    ActivityLogEntry,
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
)

pytestmark = pytest.mark.web

_KOREAN_RE = re.compile(r"[가-힣]")
_BRAND_NAME = "타쿠라이프"

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


# ---------------------------------------------------------------------------
# 누수 판정
# ---------------------------------------------------------------------------

# 보이는 문구가 되는 속성. 뒤의 둘은 확인 모달 문구·버튼 라벨 같은 data-* 문구다.
_SCAN_ATTRS = ("aria-label", "title", "placeholder", "alt")
_EXTRA_ATTRS = ("data-confirm-message", "data-label", "data-type-label", "data-category-label")


def _without_allowed(text, allowed):
    text = text.replace(_BRAND_NAME, "")
    for allowed_text in allowed:
        text = text.replace(str(allowed_text), "")
    return text


def _korean_leaks(root, scene, allowed=(), attr_allowed=()):
    """`allowed`는 모든 곳에서, `attr_allowed`는 속성값에서만 지운다(속성은 `lang`을
    못 붙인다 — 공식 행사 한글 제목이 alt·aria-label에 들어가는 경우)."""
    leaks = []
    for text, owner in root.iter_text_nodes():
        if _has_ko_ancestor(owner):
            continue
        cleaned = _without_allowed(text, allowed)
        if _KOREAN_RE.search(cleaned):
            leaks.append(f"{scene}:<{owner.tag}>:{cleaned.strip()[:40]!r}")
    for element in root.iter_elements():
        if _has_ko_ancestor(element):
            continue
        names = list(_SCAN_ATTRS) + list(_EXTRA_ATTRS)
        if element.tag == "meta":
            names.append("content")
        for name in names:
            value = element.attrs.get(name)
            if not value:
                continue
            cleaned = _without_allowed(value, [*allowed, *attr_allowed])
            if _KOREAN_RE.search(cleaned):
                leaks.append(f"{scene}:<{element.tag} {name}>:{cleaned.strip()[:40]!r}")
    return leaks


def _korean_chrome_under_explicit_lang(root, scene, allowed=()):
    """한국어 요청: 화면 문구(msgid)를 `lang` 속성이 있는 요소가 감싸면 안 된다.
    `<html>` 루트는 제외한다. 픽스처가 ASCII라 `lang` 범위 안의 한글은 곧 문구다."""
    found = []
    for text, owner in root.iter_text_nodes():
        cleaned = _without_allowed(text, allowed)
        if not _KOREAN_RE.search(cleaned):
            continue
        chain = []
        element = owner
        while element is not None:
            chain.append(element)
            element = element.parent
        # 푸터 언어 선택은 언어명을 각 언어 표기와 lang으로 보여 주므로 통째로 면제한다.
        # (option 자신의 lang을 먼저 보면 상위 form#language-switcher 면제가 가려진다.)
        if any(item.attrs.get("id") == "language-switcher" for item in chain):
            continue
        for item in chain:
            if item.tag != "html" and "lang" in item.attrs:
                found.append(f"{scene}:<{owner.tag}>:{cleaned.strip()[:40]!r}")
                break
    return found


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------

_CAL = "/archive/calendar/"
_MARCH = "month=2026-03"


def _d(offset):
    return timezone.localdate() + timedelta(days=offset)


def _at(year, month, day, hour=10, minute=30):
    return timezone.make_aware(datetime(year, month, day, hour, minute))


def _ev(make_event, title, **kwargs):
    base = {"category": "popup_store", "region": "seoul", "location_name": "Scan Hall"}
    return make_event(title=title, **{**base, **kwargs})


def _log(user, kind, when, label, **kwargs):
    return ActivityLogEntry.objects.create(
        user=user, kind=kind, occurred_at=when, subject_label=label, **kwargs
    )


def _march_month(make_event, make_user):
    """2026-03-05에 예정·찜 로그·방문·굿즈 획득·(숨은)상태 변경이 겹치는 달.

    그날 보이는 항목이 4개라 셀에 `+2`가 나오고, 5개 활동 그룹이 모두 있다."""
    user = make_user()
    kinds = ActivityLogEntry.Kind
    sched = _ev(
        make_event,
        "Scan Sched",
        start_date=datetime(2026, 3, 4).date(),
        end_date=datetime(2026, 3, 6).date(),
    )
    UserEventStatus.objects.create(user=user, event=sched, status="planned")
    heart = _ev(make_event, "Scan Heart Ev")
    _log(user, kinds.INTEREST_ADDED, _at(2026, 3, 5), "Scan Heart Ev", event=heart)
    _log(user, kinds.INTEREST_REMOVED, _at(2026, 3, 9, 8, 5), "Scan Removed Ev")
    visit_event = _ev(make_event, "Scan Visit Ev")
    VisitRecord.objects.create(user=user, event=visit_event, visited_on=datetime(2026, 3, 5).date())
    _log(user, kinds.STATUS_CHANGED, _at(2026, 3, 5, 11), "Scan Status Ev", event=visit_event)
    CollectionItem.objects.create(
        user=user, name="Scan Goods Acq", quantity=1, acquired_on=datetime(2026, 3, 5).date()
    )
    entry = PersonalEntry.objects.create(user=user, kind="place", title="Scan Cal Entry")
    VisitRecord.objects.create(
        user=user, personal_entry=entry, visited_on=datetime(2026, 3, 12).date()
    )
    return user


def _march_scene(query, *, user_input=()):
    def scene(make_event, make_user):
        return _march_month(make_event, make_user), f"{_CAL}?{query}", list(user_input)

    return scene


def _bare_scene(path):
    def scene(make_event, make_user):
        return make_user(), path, []

    return scene


def _scan_today_cluster(make_event, make_user):
    """오늘 칸에 방문·굿즈·찜(로그 없는 옛 찜)·로그 항목이 모여 `+N`·오늘 셀·시각 표기가 나온다."""
    user = make_user()
    today = _d(0)
    VisitRecord.objects.create(
        user=user, event=_ev(make_event, "Scan Today Visit"), visited_on=today
    )
    CollectionItem.objects.create(user=user, name="Scan Today Goods", quantity=1)
    EventInterest.objects.create(user=user, event=_ev(make_event, "Scan Today Heart"))
    ongoing = _ev(make_event, "Scan Today Sched", start_date=_d(-1), end_date=_d(2))
    UserEventStatus.objects.create(user=user, event=ongoing, status="planned")
    _log(user, ActivityLogEntry.Kind.INTEREST_ADDED, timezone.now(), "Scan Today Logged")
    return user, _CAL, []


def _scan_korean_user_labels(make_event, make_user):
    user = make_user()
    entry = PersonalEntry.objects.create(user=user, kind="place", title="한글 달력 장소")
    VisitRecord.objects.create(
        user=user, personal_entry=entry, visited_on=datetime(2026, 3, 5).date()
    )
    CollectionItem.objects.create(
        user=user, name="한글 달력 굿즈", quantity=1, acquired_on=datetime(2026, 3, 5).date()
    )
    return user, f"{_CAL}?{_MARCH}&date=2026-03-05", ["한글 달력 장소", "한글 달력 굿즈"]


_SCANS = {
    "month_selected_day": _march_scene(f"{_MARCH}&date=2026-03-05"),
    "month_empty_selected_day": _march_scene(f"{_MARCH}&date=2026-03-20"),
    "month_default_selected": _march_scene(_MARCH),
    "month_personal_visit_day": _march_scene(f"{_MARCH}&date=2026-03-12"),
    "month_removed_log_day": _march_scene(f"{_MARCH}&date=2026-03-09"),
    "filter_visit": _march_scene(f"{_MARCH}&date=2026-03-05&type=visit"),
    "filter_interest": _march_scene(f"{_MARCH}&date=2026-03-05&type=interest"),
    "filter_multi": _march_scene(f"{_MARCH}&date=2026-03-05&type=schedule&type=goods"),
    "filter_legacy_status": _march_scene(f"{_MARCH}&date=2026-03-05&type=status"),
    "filter_unknown_type": _march_scene(f"{_MARCH}&type=nope"),
    "search_no_match": _march_scene(f"{_MARCH}&date=2026-03-05&q=zzqq"),
    "search_no_match_with_filter": _march_scene(f"{_MARCH}&type=visit&q=zzqq"),
    "empty_month": _bare_scene(f"{_CAL}?month=2026-02"),
    "empty_default": _bare_scene(_CAL),
    "month_boundary_december": _bare_scene(f"{_CAL}?month=2026-12"),
    "month_boundary_january": _bare_scene(f"{_CAL}?month=2027-01&date=2027-01-01"),
    "leap_day": _bare_scene(f"{_CAL}?month=2028-02&date=2028-02-29"),
    "error_bad_month": _bare_scene(f"{_CAL}?month=bad"),
    "error_bad_date": _bare_scene(f"{_CAL}?{_MARCH}&date=2026-04-01"),
    "error_empty_date": _bare_scene(f"{_CAL}?{_MARCH}&date="),
    "today_cluster": _scan_today_cluster,
    "korean_user_labels": _scan_korean_user_labels,
}

# 거짓 통과 방지: 채운 장면은 픽스처 문자열이 실제로 그려져야 한다.
_EXPECTED_TEXT = {
    "month_selected_day": "Scan Goods Acq",
    "month_default_selected": "Scan Sched",
    "month_personal_visit_day": "Scan Cal Entry",
    "month_removed_log_day": "Scan Removed Ev",
    "filter_visit": "Scan Visit Ev",
    "filter_multi": "Scan Goods Acq",
    "today_cluster": "Scan Today Goods",
}

_CJK_SCENES = (
    "month_selected_day",
    "month_empty_selected_day",
    "filter_visit",
    "search_no_match",
    "empty_month",
    "error_bad_month",
    "today_cluster",
    "korean_user_labels",
)


def _lang_scene_pairs():
    pairs = [("en", scene) for scene in _SCANS]
    pairs += [(lang, scene) for lang in ("ja", "zh-hans") for scene in _CJK_SCENES]
    return pairs


# AC3
@pytest.mark.django_db
@pytest.mark.parametrize("lang, scene", _lang_scene_pairs())
def test_번역된_활동_달력에는_lang_ko_밖의_한글이_없다(make_event, make_user, lang, scene):
    user, path, allowed = _SCANS[scene](make_event, make_user)

    resp = _get(path, lang, user=user)

    assert resp.status_code == 200
    body = resp.content.decode()
    assert all(text in body for text in allowed)
    assert _EXPECTED_TEXT.get(scene, "") in body
    assert _korean_leaks(_parse(resp), f"{lang}:{scene}", allowed) == []


# AC3 한국어 짝: 화면 문구를 lang 속성이 감싸지 않는다(guardrail 21)
@pytest.mark.django_db
@pytest.mark.parametrize("scene", list(_SCANS))
def test_한국어_활동_달력은_문구를_lang_속성으로_감싸지_않는다(make_event, make_user, scene):
    user, path, allowed = _SCANS[scene](make_event, make_user)

    resp = _get(path, "ko", user=user)

    assert resp.status_code == 200
    assert _korean_chrome_under_explicit_lang(_parse(resp), scene, allowed) == []


# AC3 거짓 통과 방지: 오류 장면은 실제로 오류 패널을 그린다
@pytest.mark.django_db
@pytest.mark.parametrize(
    "scene", ["error_bad_month", "error_bad_date", "error_empty_date", "search_no_match"]
)
def test_오류_장면은_오류_패널을_그린다(make_event, make_user, scene):
    user, path, _ = _SCANS[scene](make_event, make_user)

    root = _parse(_get(path, "en", user=user))

    assert len(root.find_all(cls="calendar-error-panel")) == 1


# AC3 거짓 통과 방지: 한 날짜에 항목이 3개 넘으면 셀 요약과 선택일 목록이 모두 그려진다
@pytest.mark.django_db
def test_항목이_많은_날은_선택일_목록에_네_항목이_그려진다(make_event, make_user):
    user, path, _ = _SCANS["month_selected_day"](make_event, make_user)

    root = _parse(_get(path, "en", user=user))

    rows = root.find_all("li", cls="calendar-item-row")
    assert len(rows) == 4
    assert len(root.find_all(cls="day-cell")) >= 28


# AC3 (query_failed): 조회·그리드 실패는 오류 패널로 완화되고 영어 화면에 한글이 없다
@pytest.mark.django_db
@pytest.mark.parametrize("target", ["list_user_activity_for_month", "month_grid"])
def test_영어_활동_달력_조회_실패_화면에는_lang_ko_밖의_한글이_없다(
    make_event, make_user, monkeypatch, target
):
    def _boom(*args, **kwargs):
        raise RuntimeError("scan forced failure")

    monkeypatch.setattr(f"web.views.activity.{target}", _boom)
    user = make_user()

    resp = _get(f"{_CAL}?{_MARCH}", "en", user=user)

    assert resp.status_code == 200
    root = _parse(resp)
    assert len(root.find_all(cls="calendar-error-panel")) == 1
    assert _korean_leaks(root, f"query_failed[{target}]") == []
