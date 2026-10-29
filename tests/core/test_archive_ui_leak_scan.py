"""트랙 43-3: 영어(·일본어·중국어) 아카이브·컬렉션·마이페이지 화면에 `lang="ko"`
밖 한글이 없다는 합격 테스트(AC3). 활동 달력 장면은 `test_archive_ui_leak_scan_scenes.py`.

`test_event_ui_leak_scan.py`와 같은 방식이다: 장면 함수가 `(user, path, allowed)`를
돌려주고, 해당 언어로 요청한 뒤 파싱 트리에서 `lang="ko"` 조상이 없는 텍스트 노드와
속성(aria-label·title·placeholder·alt, meta는 content)의 한글을 찾는다. 사용자 입력과
행사 제목은 ASCII 픽스처라 한글이 나오면 곧 누수다. `tests`에 `__init__.py`가 없어
파일 간 임포트가 불안정하므로 요소 트리 파서와 요청 헬퍼는 복제했다.

사용자 입력 규칙(선례 확인 결과): 닉네임·메모·개인 항목 제목 같은 한글 사용자 입력은
번역도 `lang="ko"` 표시도 하지 않는다(prompt_plan 43-3 §2-10, 행사 스캔의 선례는 사용자
입력 자체가 없어 ASCII 픽스처만 썼다). 그래서 한글 사용자 입력은 `allowed`에 넣어
모든 텍스트 노드·스캔 속성에서 그 문자열만 지우고 나머지(화면 문구)를 검사한다. 지울 문자열은
응답에 실제로 있어야 한다(거짓 통과 방지).

못 잡는 곳: 서버 렌더 밖(JS가 만드는 문구)은 이 테스트로 볼 수 없다. HTML 속성은
`value=`·`data-*`(아래 `_EXTRA_ATTRS` 몇 개 제외)를 보지 않는다.
`.mo`가 로컬에 컴파일돼 있어야 한다(`uv run django-admin compilemessages --ignore .venv`).
"""

import re
from datetime import timedelta
from html.parser import HTMLParser
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from django.test import Client
from django.utils import timezone

from archive.models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)
from core.vocab import CATEGORY_SOURCE_LABELS

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
# 픽스처 헬퍼(tests/archive/conftest.py는 tests/core에서 쓸 수 없어 직접 만든다)
# ---------------------------------------------------------------------------


def _d(offset):
    return timezone.localdate() + timedelta(days=offset)


def _ev(make_event, title, **kwargs):
    base = {
        "category": "popup_store",
        "region": "seoul",
        "location_name": "Scan Hall",
        "work_title": "Scan Work",
    }
    return make_event(title=title, **{**base, **kwargs})


def _entry(user, title, **kwargs):
    return PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title=title, **kwargs
    )


def _visit(user, visited_on, **kwargs):
    return VisitRecord.objects.create(user=user, visited_on=visited_on, **kwargs)


def _photos(record, count):
    # 파일 이름만 저장한다 — 디스크에 쓰지 않고 `.url` 렌더만 확인한다.
    for index in range(count):
        VisitRecordPhoto.objects.create(
            visit_record=record, image=f"visit_photos/scan_{record.pk}_{index}.png"
        )


def _item(user, name, **kwargs):
    return CollectionItem.objects.create(user=user, name=name, **kwargs)


def _events(make_event):
    return SimpleNamespace(
        past=_ev(make_event, "Scan Past", start_date=_d(-10), end_date=_d(-8)),
        past2=_ev(
            make_event,
            "Scan Past Two",
            category="exhibition",
            start_date=_d(-20),
            end_date=_d(-18),
        ),
        ongoing=_ev(make_event, "Scan Ongoing", start_date=_d(-2), end_date=_d(5)),
        upcoming=_ev(make_event, "Scan Upcoming", start_date=_d(3), end_date=_d(9)),
        undated=_ev(make_event, "Scan Undated"),
    )


def _entries(user):
    """저장된 한국어 어휘 카테고리·자유 입력 카테고리·카테고리 없음·공식 제보됨."""
    return [
        _entry(
            user,
            "Scan Entry One",
            category="카페",
            location_name="Scan Spot",
            memo="scan memo",
            url="https://example.com/one",
        ),
        _entry(user, "Scan Entry Two", category="Scan Free Cat"),
        _entry(user, "Scan Entry Three"),
        _entry(
            user,
            "Scan Entry Four",
            category="팝업스토어",
            promotion_status=PersonalEntry.PromotionStatus.SUBMITTED,
        ),
    ]


def _statuses(user, events, entries):
    status = UserEventStatus.Status
    for event, value in (
        (events.past, status.VISITED),
        (events.ongoing, status.PLANNED),
        (events.upcoming, status.PLANNED),
        (events.past2, status.PLANNED),  # 종료된 행사의 예정 → 파생 놓침
        (events.undated, status.MISSED),
    ):
        UserEventStatus.objects.create(user=user, event=event, status=value)
    UserEventStatus.objects.create(user=user, personal_entry=entries[0], status=status.PLANNED)
    UserEventStatus.objects.create(user=user, personal_entry=entries[1], status=status.VISITED)


def _visits(user, events, entries):
    reviewed = _visit(user, _d(-9), event=events.past, short_review="scan review")
    one_photo = _visit(user, _d(-1), event=events.ongoing, short_review="scan photo review")
    _photos(one_photo, 1)
    many_photos = _visit(user, _d(-19), event=events.past2)
    _photos(many_photos, 3)
    personal_vocab = _visit(
        user, _d(-7), personal_entry=entries[0], short_review="scan vocab review"
    )
    personal_free = _visit(user, _d(-6), personal_entry=entries[1])
    return SimpleNamespace(
        reviewed=reviewed,
        one_photo=one_photo,
        many_photos=many_photos,
        personal_vocab=personal_vocab,
        personal_free=personal_free,
    )


def _items(user, events, visits):
    """보유·구함·교환·미보유 배지와 수량 0·1·2가 모두 나오는 굿즈."""
    return [
        _item(
            user,
            "Scan Both",
            quantity=2,
            tradeable_quantity=1,
            is_wanted=True,
            work_title="Scan Work",
            item_type="키링",
        ),
        _item(user, "Scan One", quantity=1, work_title="Scan Work"),
        _item(user, "Scan Wanted Only", quantity=0, is_wanted=True, work_title="Scan Work Two"),
        _item(user, "Scan None", quantity=0, work_title="Scan Work Two"),
        _item(user, "Scan Trade", quantity=2, tradeable_quantity=2, work_title="Scan Work Three"),
        _item(
            user,
            "Scan Linked",
            quantity=1,
            work_title="Scan Work",
            item_type="Scan Free Type",
            character_name="Scan Char",
            acquired_on=_d(-9),
            acquisition_source="Scan Source",
            event=events.past,
            visit_record=visits.reviewed,
            memo="scan item memo",
            image="collection/scan_linked.png",
        ),
        _item(user, "Scan Personal Link", quantity=1, visit_record=visits.personal_free),
    ]


def _world(make_event, make_user):
    user = make_user()
    events = _events(make_event)
    entries = _entries(user)
    _statuses(user, events, entries)
    visits = _visits(user, events, entries)
    items = _items(user, events, visits)
    for event in (events.ongoing, events.upcoming, events.past, events.undated):
        EventInterest.objects.create(user=user, event=event)
    EventInterest.objects.create(user=user, personal_entry=entries[2])
    return SimpleNamespace(user=user, events=events, entries=entries, visits=visits, items=items)


def _many_statuses(user, make_event, count):
    for index in range(count):
        UserEventStatus.objects.create(
            user=user, event=_ev(make_event, f"Scan Extra {index:02d}"), status="planned"
        )


# ---------------------------------------------------------------------------
# 장면: 사용자 + 상태 만들기(경로에 world의 pk를 `{w.…}`로 끼운다)
# ---------------------------------------------------------------------------


def _world_scene(path):
    def scene(make_event, make_user):
        world = _world(make_event, make_user)
        return world.user, path.format(w=world), []

    return scene


def _bare_scene(path):
    def scene(make_event, make_user):
        return make_user(), path, []

    return scene


_POPUP_TOKEN = quote(f"cat:{CATEGORY_SOURCE_LABELS['popup_store']}")

_BARE_PATHS = {
    "mypage_empty": "/mypage/",
    "index_empty": "/archive/",
    "statuses_empty": "/archive/statuses/",
    "interests_empty": "/archive/interests/",
    "visits_empty": "/archive/visits/",
    "visit_create_empty": "/archive/visits/new/",
    "personal_empty": "/archive/personal/",
    "personal_create": "/archive/personal/new/",
    "collection_onboarding": "/collection/",
    "collection_create_empty": "/collection/new/",
}

_WORLD_PATHS = {
    "mypage_filled": "/mypage/",
    "index_filtered": "/archive/?status=visited&q=Scan",
    "index_filter_empty": "/archive/?q=zzqq",
    "index_partial": "/archive/?partial=1&q=Scan",
    "statuses_missed_filter": "/archive/statuses/?status=missed",
    "statuses_partial_empty": "/archive/statuses/?partial=1&q=zzqq",
    "interests_partial": "/archive/interests/?partial=1&q=Scan",
    "interests_no_match": "/archive/interests/?q=zzqq",
    "visits_filled": "/archive/visits/",
    "visits_oldest": "/archive/visits/?sort=oldest",
    "visits_official_category_filter": f"/archive/visits/?filter={_POPUP_TOKEN}",
    "visits_personal_category_filter": f"/archive/visits/?filter={quote('cat:Scan Free Cat')}",
    "visits_unofficial_filter": "/archive/visits/?filter=unofficial",
    "visits_search_empty": "/archive/visits/?q=zzqq",
    "visits_partial": "/archive/visits/?partial=1&q=Scan",
    "visit_detail_full": "/archive/visits/{w.visits.reviewed.pk}/",
    "visit_detail_one_photo": "/archive/visits/{w.visits.one_photo.pk}/",
    "visit_detail_many_photos": "/archive/visits/{w.visits.many_photos.pk}/",
    "visit_detail_personal": "/archive/visits/{w.visits.personal_vocab.pk}/",
    "visit_create": "/archive/visits/new/",
    "visit_create_preselect_event": "/archive/visits/new/?subject=event:{w.events.past.pk}",
    "visit_create_preselect_personal": "/archive/visits/new/?subject=personal:{w.entries[0].pk}",
    "visit_edit_official": "/archive/visits/{w.visits.many_photos.pk}/edit/",
    "visit_edit_reviewed": "/archive/visits/{w.visits.reviewed.pk}/edit/",
    "visit_edit_personal": "/archive/visits/{w.visits.personal_free.pk}/edit/",
    "personal_filled": "/archive/personal/",
    "personal_search_empty": "/archive/personal/?q=zzqq",
    "personal_partial": "/archive/personal/?partial=1&q=Scan",
    "personal_edit_vocab_category": "/archive/personal/{w.entries[0].pk}/edit/",
    "personal_edit_free_category": "/archive/personal/{w.entries[1].pk}/edit/",
    "personal_detail_with_visits": "/archive/personal/{w.entries[0].pk}/",
    "personal_detail_submitted": "/archive/personal/{w.entries[3].pk}/",
    "personal_detail_bare": "/archive/personal/{w.entries[2].pk}/",
    "collection_filled": "/collection/",
    "collection_list_view": "/collection/?view=list",
    "collection_filter_empty": "/collection/?owned=true&q=zzqq",
    "collection_unknown_work": "/collection/?work_title=Nope",
    "collection_partial": "/collection/?partial=1&q=Scan",
    "collection_partial_empty": "/collection/?partial=1&q=zzqq",
    "collection_create": "/collection/new/",
    "collection_create_preselect": "/collection/new/?visit_record={w.visits.reviewed.pk}",
    "collection_edit_linked": "/collection/{w.items[5].pk}/edit/",
    "collection_edit_plain": "/collection/{w.items[0].pk}/edit/",
    "collection_detail_linked": "/collection/{w.items[5].pk}/",
    "collection_detail_both": "/collection/{w.items[0].pk}/",
    "collection_detail_none": "/collection/{w.items[3].pk}/",
    "collection_detail_wanted": "/collection/{w.items[2].pk}/",
    "collection_detail_personal_visit": "/collection/{w.items[6].pk}/",
}
for _query in (  # 파생 필터(보유·구함·교환·중복·미보유)와 작품·캐릭터·유형 필터
    "owned=true",
    "is_wanted=true",
    "tradeable=true",
    "duplicate=true",
    "owned=false",
    "work_title=Scan+Work&character_name=Scan+Char",
    "item_type=Scan+Free+Type&view=list",
):
    _WORLD_PATHS[f"collection_filter[{_query}]"] = f"/collection/?{_query}"


def _scan_index_filled(make_event, make_user):
    world = _world(make_event, make_user)
    _many_statuses(world.user, make_event, 8)
    return world.user, "/archive/?sort=created_at&page=2", []


def _scan_statuses_filled(make_event, make_user):
    world = _world(make_event, make_user)
    _many_statuses(world.user, make_event, 4)
    return world.user, "/archive/statuses/?sort=created_at", []


def _scan_interests_filled(make_event, make_user):
    world = _world(make_event, make_user)
    for index in range(10):
        EventInterest.objects.create(
            user=world.user, event=_ev(make_event, f"Scan Heart {index:02d}", start_date=_d(4))
        )
    return world.user, "/archive/interests/?page=2&sort=oldest", []


def _scan_visits_paged(make_event, make_user):
    world = _world(make_event, make_user)
    for index in range(6):
        _visit(world.user, _d(-30 - index), event=_ev(make_event, f"Scan Many {index}"))
    return world.user, "/archive/visits/?page=2", []


def _scan_personal_paged_oldest(make_event, make_user):
    world = _world(make_event, make_user)
    for index in range(4):
        _entry(world.user, f"Scan Bulk {index}")
    return world.user, "/archive/personal/?page=2&sort=oldest", []


def _scan_collection_paged(make_event, make_user):
    world = _world(make_event, make_user)
    for index in range(6):
        _item(world.user, f"Scan Bulk {index}", quantity=index % 3, work_title="Scan Work Bulk")
    return world.user, "/collection/?page=2", []


# ---------------------------------------------------------------------------
# 한글 사용자 입력 장면(스캔 사각지대 고정)
# ---------------------------------------------------------------------------

_KO_MEMO = "한글 메모 내용"
_KO_ENTRY_TITLE = "한글 개인 항목 제목"
_KO_REVIEW = "한글 후기"
_KO_ITEM_NAME = "한글 굿즈 이름"


def _scan_korean_memo_personal_edit(make_event, make_user):
    user = make_user()
    entry = _entry(user, "Scan Memo Entry", memo=_KO_MEMO, category="Scan Free Cat")
    return user, f"/archive/personal/{entry.pk}/edit/", [_KO_MEMO]


def _scan_korean_memo_personal_detail(make_event, make_user):
    user = make_user()
    entry = _entry(user, "Scan Memo Entry", memo=_KO_MEMO)
    return user, f"/archive/personal/{entry.pk}/", [_KO_MEMO]


def _scan_korean_titles_personal_list(make_event, make_user):
    user = make_user()
    _entry(user, _KO_ENTRY_TITLE, category="카페")
    _entry(user, "Scan Entry Ascii")
    return user, "/archive/personal/", [_KO_ENTRY_TITLE]


def _scan_korean_titles_visits(make_event, make_user):
    user = make_user()
    entry = _entry(user, _KO_ENTRY_TITLE)
    _visit(user, _d(-2), personal_entry=entry, short_review=_KO_REVIEW)
    return user, "/archive/visits/", [_KO_ENTRY_TITLE, _KO_REVIEW]


def _scan_korean_review_visit_edit(make_event, make_user):
    user = make_user()
    entry = _entry(user, "Scan Review Entry")
    record = _visit(user, _d(-2), personal_entry=entry, short_review=_KO_REVIEW)
    return user, f"/archive/visits/{record.pk}/edit/", [_KO_REVIEW]


def _scan_korean_collection_edit(make_event, make_user):
    user = make_user()
    item = _item(user, _KO_ITEM_NAME, quantity=1, memo=_KO_MEMO)
    return user, f"/collection/{item.pk}/edit/", [_KO_ITEM_NAME, _KO_MEMO]


def _scan_korean_collection_list(make_event, make_user):
    user = make_user()
    _item(user, _KO_ITEM_NAME, quantity=1, memo=_KO_MEMO)
    # 메모는 목록 보기에서만 렌더된다(기본 격자 보기에는 없다).
    return user, "/collection/?view=list", [_KO_ITEM_NAME, _KO_MEMO]


# ---------------------------------------------------------------------------
# 장면 모음
# ---------------------------------------------------------------------------

_SCANS = {
    **{name: _bare_scene(path) for name, path in _BARE_PATHS.items()},
    **{name: _world_scene(path) for name, path in _WORLD_PATHS.items()},
    "index_filled_paged": _scan_index_filled,
    "statuses_filled": _scan_statuses_filled,
    "interests_filled_paged": _scan_interests_filled,
    "visits_paged": _scan_visits_paged,
    "personal_paged_oldest": _scan_personal_paged_oldest,
    "collection_paged": _scan_collection_paged,
    "korean_memo_personal_edit": _scan_korean_memo_personal_edit,
    "korean_memo_personal_detail": _scan_korean_memo_personal_detail,
    "korean_titles_personal_list": _scan_korean_titles_personal_list,
    "korean_titles_visits": _scan_korean_titles_visits,
    "korean_review_visit_edit": _scan_korean_review_visit_edit,
    "korean_collection_edit": _scan_korean_collection_edit,
    "korean_collection_list": _scan_korean_collection_list,
}


# 거짓 통과 방지: 채운 장면은 픽스처 문자열이 실제로 그려져야 한다.
_EXPECTED_TEXT = {
    "index_filled_paged": "Scan",
    "index_filtered": "Scan Past",
    "statuses_filled": "Scan",
    "interests_filled_paged": "Scan Heart",
    "visits_filled": "Scan Past",
    "visits_official_category_filter": "Scan Past",
    "visits_personal_category_filter": "Scan Entry Two",
    "visits_unofficial_filter": "Scan Entry One",
    "visit_detail_full": "Scan Linked",
    "personal_filled": "Scan Entry One",
    "personal_detail_with_visits": "Scan Entry One",
    "collection_filled": "Scan Both",
    "collection_detail_linked": "Scan Past",
    "collection_edit_linked": "Scan Linked",
}

# 일본어·중국어는 대표 장면에서만 본다(전체는 영어).
_CJK_SCENES = (
    "mypage_filled",
    "index_filled_paged",
    "statuses_filled",
    "interests_filled_paged",
    "visits_filled",
    "visit_detail_full",
    "visit_create",
    "visit_edit_official",
    "personal_filled",
    "personal_create",
    "personal_edit_vocab_category",
    "personal_detail_with_visits",
    "collection_onboarding",
    "collection_filled",
    "collection_create",
    "collection_edit_linked",
    "collection_detail_linked",
    "collection_filter_empty",
    "collection_partial",
    "korean_memo_personal_edit",
)


def _lang_scene_pairs():
    pairs = [("en", scene) for scene in _SCANS]
    pairs += [(lang, scene) for lang in ("ja", "zh-hans") for scene in _CJK_SCENES]
    return pairs


# AC3
@pytest.mark.django_db
@pytest.mark.parametrize("lang, scene", _lang_scene_pairs())
def test_번역_화면에는_lang_ko_밖의_한글이_없다(make_event, make_user, lang, scene):
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
def test_한국어_화면은_문구를_lang_속성으로_감싸지_않는다(make_event, make_user, scene):
    user, path, allowed = _SCANS[scene](make_event, make_user)

    resp = _get(path, "ko", user=user)

    assert resp.status_code == 200
    assert _korean_chrome_under_explicit_lang(_parse(resp), scene, allowed) == []


# AC3 거짓 통과 방지(스캔 사각지대): 한글 메모는 영어 수정 화면 textarea에 글자 그대로 남는다
@pytest.mark.django_db
def test_영어_수정_화면의_한글_메모는_번역되지_않고_textarea에_그대로_남는다(make_event, make_user):
    user, path, _ = _scan_korean_memo_personal_edit(make_event, make_user)

    root = _parse(_get(path, "en", user=user))

    areas = root.find_all("textarea", attrs={"name": "memo"})
    assert len(areas) == 1
    assert areas[0].text() == _KO_MEMO


# AC3 거짓 통과 방지: 한글 허용 문자열 말고는 아무것도 가려지지 않는다
@pytest.mark.django_db
def test_허용_문자열을_지워도_나머지_한글은_누수로_잡힌다(make_event, make_user):
    user, path, allowed = _scan_korean_titles_personal_list(make_event, make_user)
    root = _parse(_get(path, "ko", user=user))
    # 한국어 화면은 루트가 <html lang="ko">라 모든 텍스트가 ko 범위 안이다(가드레일 21).
    # 점검용으로 루트 lang을 빼야 문구가 범위 밖 한글로 보인다.
    for html in root.find_all("html"):
        html.attrs.pop("lang", None)

    leaks = _korean_leaks(root, "probe", allowed)

    assert leaks, "한국어 화면에서는 허용 문자열 밖의 한글이 누수로 잡혀야 한다"
    assert all(_KO_ENTRY_TITLE[:4] not in leak for leak in leaks)


# ---------------------------------------------------------------------------
# 공식 행사 한글 제목: 본문은 lang="ko" 범위, 속성(alt·aria-label)만 면제
# ---------------------------------------------------------------------------

_OFFICIAL_KO_TITLE = "스캔 공식 행사"
_OFFICIAL_KO_PLACE = "스캔 장소"
_OFFICIAL_KO_PLANNED = "스캔 예정 행사"


def _ko_world(make_event, make_user):
    user = make_user()
    event = _ev(
        make_event,
        _OFFICIAL_KO_TITLE,
        location_name=_OFFICIAL_KO_PLACE,
        work_title="Scan Work",
        start_date=_d(-10),
        end_date=_d(-8),
    )
    planned = _ev(
        make_event,
        _OFFICIAL_KO_PLANNED,
        location_name=_OFFICIAL_KO_PLACE,
        start_date=_d(3),
        end_date=_d(4),
    )
    UserEventStatus.objects.create(user=user, event=event, status="visited")
    UserEventStatus.objects.create(user=user, event=planned, status="planned")
    EventInterest.objects.create(user=user, event=event)
    record = _visit(user, _d(-9), event=event, short_review="scan review")
    _photos(record, 2)
    return user, event, record


def _ko_official(path_of, needle=_OFFICIAL_KO_TITLE):
    def scene(make_event, make_user):
        user, event, record = _ko_world(make_event, make_user)
        return user, path_of(event, record), needle

    return scene


_OFFICIAL_KO_SCENES = {
    "index": _ko_official(lambda event, record: "/archive/"),
    "statuses": _ko_official(lambda event, record: "/archive/statuses/"),
    "interests": _ko_official(lambda event, record: "/archive/interests/"),
    "visits": _ko_official(lambda event, record: "/archive/visits/"),
    "visit_detail": _ko_official(lambda event, record: f"/archive/visits/{record.pk}/"),
    "visit_edit": _ko_official(lambda event, record: f"/archive/visits/{record.pk}/edit/"),
    "visit_create": _ko_official(
        lambda event, record: "/archive/visits/new/", _OFFICIAL_KO_PLANNED
    ),
}


# AC3 (WED S-1: 공식 행사의 제목·장소는 영어 화면에서 lang="ko")
@pytest.mark.django_db
@pytest.mark.parametrize("scene", list(_OFFICIAL_KO_SCENES))
def test_영어_화면의_공식_행사_한글_제목과_장소는_lang_ko_범위다(make_event, make_user, scene):
    user, path, needle = _OFFICIAL_KO_SCENES[scene](make_event, make_user)

    resp = _get(path, "en", user=user)

    assert resp.status_code == 200
    assert needle in resp.content.decode()
    leaks = _korean_leaks(
        _parse(resp),
        scene,
        attr_allowed=[_OFFICIAL_KO_TITLE, _OFFICIAL_KO_PLANNED, _OFFICIAL_KO_PLACE],
    )
    assert leaks == []
