"""
core/vocab.py — takulife 도메인 어휘의 단일 출처.

이 모듈은 카테고리, 지역, archive 상태, event 상태의 표준 slug→label
매핑을 정의한다. 모든 템플릿, 컨텍스트 프로세서, 앞으로 만들 필터
검증기는 각자 로컬 사본을 두지 말고 이 상수를 참조해야 한다.

설계 결정:
- slug 키(왼쪽)는 API가 저장·필터링에 쓰는 값이다.
- 라벨(오른쪽)은 UI가 표시하는 값이며 요청 언어로 번역된다(원문은 한국어).
- archive/user-event 상태의 표준 CSS 클래스는 slug 그 자체다
  (interested / planned / visited / missed) — 초기 목업 템플릿의
  wish/plan/done/miss 클래스명을 대체한다.
- 순수 튜플/딕셔너리로 노출한다(매직 없음, 메타클래스 없음, 불변에 친화적).
- 라벨은 지연 번역 문자열(gettext_lazy)이라 str이 아닐 수 있다. 카테고리는
  한국어 원문 `CATEGORY_SOURCE_LABELS`(저장·필터 토큰용)도 따로 둔다.
"""
import unicodedata

from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext, gettext_lazy as _, gettext_noop

# ---------------------------------------------------------------------------
# 행사 카테고리 어휘
# slug → 표시 라벨
# ---------------------------------------------------------------------------
# 한국어 원문은 gettext_noop으로만 표시해 번역 추출 대상으로 삼고, 앱 로딩 중
# 임포트되는 이 모듈에서 번역을 미리 평가하지 않는다.
_CATEGORY_SOURCE: tuple[tuple[str, str], ...] = (
    ("popup_store", gettext_noop("팝업스토어")),
    ("collaboration_cafe", gettext_noop("콜라보 카페")),
    ("theater_bonus", gettext_noop("극장 특전")),
    ("goods_reservation", gettext_noop("굿즈 예약")),
    ("exhibition", gettext_noop("전시")),
    ("fan_meeting", gettext_noop("팬미팅")),
    ("concert", gettext_noop("콘서트")),
)

# 표시용은 요청 언어에 따라 바뀌는 지연 번역 라벨이다.
CATEGORY: tuple[tuple[str, str], ...] = tuple(
    (slug, _(label)) for slug, label in _CATEGORY_SOURCE
)

# O(1) 라벨 조회용 편의 딕셔너리.
CATEGORY_LABELS: dict[str, str] = dict(CATEGORY)

# 요청 언어와 무관한 한국어 원문(방문 기록 필터 토큰처럼 저장값과 맞대는 용도).
CATEGORY_SOURCE_LABELS: dict[str, str] = dict(_CATEGORY_SOURCE)

# ---------------------------------------------------------------------------
# 지역 어휘
# slug → 표시 라벨
# ---------------------------------------------------------------------------
REGION: tuple[tuple[str, str], ...] = (
    ("seoul", _("서울")),
    ("gyeonggi", _("경기")),
    ("incheon", _("인천")),
    ("busan", _("부산")),
    # 실데이터가 이미 대구·대전·광주를 쓰고 있었는데 어휘에 없어 지역
    # 필터 어디에도 걸리지 않았다 — 어휘 가드를 걸기 전에 먼저 메워야
    # 했던 구멍이다.
    ("daegu", _("대구")),
    ("daejeon", _("대전")),
    ("gwangju", _("광주")),
    ("online", _("온라인")),
)

REGION_LABELS: dict[str, str] = dict(REGION)

# ---------------------------------------------------------------------------
# Archive / user-event 상태 어휘
# 사용자가 추적 중인 행사에 부여하는 상태들이다.
# slug가 곧 표준 CSS 클래스명이다.
# slug → 표시 라벨
# ---------------------------------------------------------------------------
ARCHIVE_STATUS: tuple[tuple[str, str], ...] = (
    ("planned", _("방문 예정")),
    ("visited", _("방문 완료")),
    ("missed", _("놓침")),
)

ARCHIVE_STATUS_LABELS: dict[str, str] = dict(ARCHIVE_STATUS)


# ---------------------------------------------------------------------------
# 컬렉션 항목 종류 어휘
# 모델에는 자유 입력(DB choices 제약 없음)이며, 이건 CollectionItem.item_type에
# 대한 UI 쪽 안내일 뿐이다. slug → 표시 라벨
# ---------------------------------------------------------------------------
_COLLECTION_ITEM_TYPE_SOURCE: tuple[tuple[str, str], ...] = (
    ("acrylic_stand", gettext_noop("아크릴 스탠드")),
    ("keyring", gettext_noop("키링")),
    ("badge", gettext_noop("뱃지")),
    ("photocard", gettext_noop("포토카드")),
    ("plush", gettext_noop("인형")),
    ("stationery", gettext_noop("문구")),
    ("etc", gettext_noop("기타")),
)

COLLECTION_ITEM_TYPE: tuple[tuple[str, str], ...] = tuple(
    (slug, _(label)) for slug, label in _COLLECTION_ITEM_TYPE_SOURCE
)

# 요청 언어와 무관한 한국어 원문(저장값과 맞대는 용도).
COLLECTION_ITEM_TYPE_SOURCE_LABELS: tuple[str, ...] = tuple(
    label for _slug, label in _COLLECTION_ITEM_TYPE_SOURCE
)

COLLECTION_ITEM_TYPE_LABELS: dict[str, str] = dict(COLLECTION_ITEM_TYPE)


def archive_status_label(slug: str) -> str:
    return ARCHIVE_STATUS_LABELS.get(slug, slug)


# ---------------------------------------------------------------------------
# Archive 상태 목록 정렬 어휘(slug는
# archive.queries.ARCHIVE_STATUS_SORT_ORDERING과 일치). 빈 slug ""가 기본값
# (최근 수정순 / -updated_at). slug → 표시 라벨
# ---------------------------------------------------------------------------
ARCHIVE_STATUS_SORT: tuple[tuple[str, str], ...] = (
    ("", _("최근 수정순")),
    ("created_at", _("등록순")),
)

ARCHIVE_STATUS_SORT_LABELS: dict[str, str] = dict(ARCHIVE_STATUS_SORT)

# ---------------------------------------------------------------------------
# Archive 방문 기록 목록 정렬 어휘(slug는
# archive.queries.ARCHIVE_VISIT_SORT_ORDERING과 일치). 빈 slug ""가 기본값
# (최근 방문순 / -visited_on, -id). slug → 표시 라벨
# ---------------------------------------------------------------------------
ARCHIVE_VISIT_SORT: tuple[tuple[str, str], ...] = (
    ("", _("최근 방문순")),
    ("oldest", _("오래된 방문순")),
)

ARCHIVE_VISIT_SORT_LABELS: dict[str, str] = dict(ARCHIVE_VISIT_SORT)

# ---------------------------------------------------------------------------
# Archive 비공식 등록 목록 정렬 어휘(slug는
# archive.queries.ARCHIVE_PERSONAL_SORT_ORDERING과 일치). 빈 slug ""가
# 기본값(최근 등록순 / -created_at, -id). slug → 표시 라벨
# ---------------------------------------------------------------------------
ARCHIVE_PERSONAL_SORT: tuple[tuple[str, str], ...] = (
    ("", _("최근 등록순")),
    ("oldest", _("오래된 등록순")),
)

ARCHIVE_PERSONAL_SORT_LABELS: dict[str, str] = dict(ARCHIVE_PERSONAL_SORT)

# ---------------------------------------------------------------------------
# Archive 찜 목록 정렬 어휘(slug는 archive.queries.list_user_interests의
# 내부 정렬과 일치). 빈 slug ""가 기본값(최근 찜순 / -id). slug → 표시 라벨
# ---------------------------------------------------------------------------
ARCHIVE_INTEREST_SORT: tuple[tuple[str, str], ...] = (
    ("", _("최근 찜순")),
    ("oldest", _("오래된 찜순")),
)

ARCHIVE_INTEREST_SORT_LABELS: dict[str, str] = dict(ARCHIVE_INTEREST_SORT)

# ---------------------------------------------------------------------------
# 비공식 등록 카테고리 제안(직접 등록 작성 페이지). `choices` 제약이 아니라
# 자유 입력을 돕는 힌트 칩이다 — PersonalEntry.category는 평범한
# CharField라 어떤 자유 텍스트도 받아들여진다(위 COLLECTION_ITEM_TYPE의
# "UI 쪽 안내일 뿐" 원칙과 같다).
# ---------------------------------------------------------------------------
_PERSONAL_ENTRY_CATEGORY_SOURCE: tuple[str, ...] = (
    gettext_noop("카페"),
    gettext_noop("팝업스토어"),
    gettext_noop("전시"),
    gettext_noop("성지순례"),
    gettext_noop("굿즈숍"),
    gettext_noop("기타"),
)

PERSONAL_ENTRY_CATEGORY_SUGGESTIONS: tuple[str, ...] = tuple(
    _(label) for label in _PERSONAL_ENTRY_CATEGORY_SOURCE
)

# ---------------------------------------------------------------------------
# 행사 상태 어휘(archive 상태와 독립된 축)
# Event 객체의 공개/시간적 상태를 나타낸다.
# slug → 표시 라벨
# ---------------------------------------------------------------------------
EVENT_STATUS: tuple[tuple[str, str], ...] = (
    ("upcoming", _("예정")),
    ("ongoing", _("진행 중")),
    ("closing_soon", _("종료 임박")),
    ("ended", _("종료")),
)

EVENT_STATUS_LABELS: dict[str, str] = dict(EVENT_STATUS)
# "all"은 목록 화면 전용 필터 값일 뿐 EVENT_STATUS의 멤버가 아니다: 그
# 튜플은 templates/core/events/calendar.html이 상태 라디오를 그리는 데도
# 쓰이는데, 달력의 상태 필터는 이미 value="" 라디오로 "전체 상태"를
# 기본값으로 삼고 있어 "all"을 EVENT_STATUS에 넣으면 "전체" 라디오가
# 중복으로 하나 더 생긴다. 이 라벨 전용 항목은 목록 화면의 status=all이
# 활성일 때 _active_filter_chips(core/views.py)가 원문 "all" 대신 사람이
# 읽을 라벨을 보여줄 수 있게 하기 위해서만 존재한다.
EVENT_STATUS_LABELS["all"] = _("전체")

# ---------------------------------------------------------------------------
# 공개 목록 정렬 어휘(event_list 정렬).
# 빈 slug ""가 기본 정렬. slug → 표시 라벨
# ---------------------------------------------------------------------------
EVENT_SORT: tuple[tuple[str, str], ...] = (
    ("", _("기본순")),
    ("closing_soon", _("종료 임박순")),
    ("start_asc", _("시작일 빠른순")),
    ("newest", _("최신 등록순")),
)

EVENT_SORT_LABELS: dict[str, str] = dict(EVENT_SORT)

# ---------------------------------------------------------------------------
# 스태프 콘솔 목록 정렬 어휘. EVENT_SORT와 슬러그 "" 하나만 겹치고 나머지는
# 다른 목록이다: 공개 목록 기본값(EVENT_SORT[""])은 "기본순"(진행중/예정/종료
# 우선순위)인데, 스태프 기본값은 등록 최신순(-created_at)이다. 같은 슬러그가
# 화면마다 다른 동작을 가리키게 되므로 라벨·집합을 분리해 둔다.
# slug → 표시 라벨
# ---------------------------------------------------------------------------
STAFF_EVENT_SORT: tuple[tuple[str, str], ...] = (
    ("", "등록 최신순"),
    ("closing_soon", "종료 임박순"),
    ("start_asc", "시작일 빠른순"),
)

STAFF_EVENT_SORT_LABELS: dict[str, str] = dict(STAFF_EVENT_SORT)


# ---------------------------------------------------------------------------
# 어휘 소속 검사.
#
# Event.category / Event.region은 `choices` 없는 평범한 CharField라
# 모델이나 DB 레이어에서 이 튜플 밖의 값을 막지 못한다. LLM 추출 경로는
# 이미 같은 어휘로 재검증하고(drafts/llm_extraction.py) 공개 API는
# 읽기 전용이지만, 스태프 쓰기 경로는 템플릿 <select>에만 의존했다 —
# 수작업 POST가 그대로 통과해 "카페/팝업" 같은 자유 텍스트가 개발 DB에
# 들어가 카테고리 색상 시스템을 조용히 무력화한 적이 있다.
#
# 예외를 던지지 않고 bool을 반환한다: 각 호출자가 자신의 레이어에 맞는
# 도메인 오류를 직접 다룬다(events.services는 PublishEvent*Error를
# 던지고 스태프 콘솔이 필드 오류로 매핑, drafts.services는
# DraftVocabError를 던진다).
#
# 모델에 `choices=`를 쓰는 방법도 검토했지만 기각했다: 이 프로젝트는
# events용 ModelForm이 없고(스태프 콘솔이 form_values를 수작업으로
# 만든다) CATEGORY_LABELS가 이미 표시를 담당하므로 얻는 게 없이 어휘를
# 고칠 때마다 AlterField 마이그레이션만 늘어난다 — 그리고 이 어휘는
# 실제로 계속 늘어나고 있다(REGION 추가 사례 참고).
# ---------------------------------------------------------------------------
def is_valid_category(value: str) -> bool:
    """`value`가 알려진 카테고리 slug이거나 ""(미분류)이면 True.

    빈 값은 일부러 유효하다: Event에서 카테고리는 선택 항목이라, 빈 값을
    거부하면 카테고리 없는 행사를 아예 등록할 수 없게 된다.

    DB(Category)를 본다 — core.models와의 순환 임포트를 피하려고
    core.categories.category_exists를 경유한다(그 함수가 호출 시점에
    core.models를 임포트한다). 비활성 카테고리도 유효 취급한다(비활성 ≠
    삭제 — 이미 그 슬러그로 저장된 이벤트의 재게시를 막으면 안 된다).
    """
    if value == "":
        return True
    from core.categories import category_exists

    return category_exists(value)


def is_valid_region(value: str) -> bool:
    """`value`가 알려진 지역 slug이거나 ""(지역 미상)이면 True.

    빈 값은 일부러 유효하다 — is_valid_category 참고.
    """
    return value == "" or value in REGION_LABELS


# ---------------------------------------------------------------------------
# 자유 입력 어휘(개인 항목 분류·굿즈 유형) 정규화.
# 저장값은 언어와 무관한 한국어 원문이다. 사용자가 어느 언어의 칩 문구를
# 보냈든 한국어 원문으로 되돌리고, 어휘 밖 값은 그대로 둔다.
# ---------------------------------------------------------------------------
def _fold(text: str) -> str:
    """대소문자·공백·라틴 악센트 차이를 지운 비교용 키.

    악센트 제거는 라틴 문자에만 한다 — 일본어 탁점·반탁점이나 한글 자모까지
    지우면 서로 다른 글자가 같은 키가 된다.
    """
    decomposed = unicodedata.normalize("NFKD", text.strip())
    kept: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch) and kept and ord(kept[-1]) < 0x250:
            continue
        kept.append(ch)
    return unicodedata.normalize("NFKC", "".join(kept)).casefold()


def _normalize_to_source(value: str, sources: tuple[str, ...]) -> str:
    folded = _fold(value)
    if not folded:
        return value
    other_languages = [code for code, _name in settings.LANGUAGES if code != "ko"]
    for source in sources:
        if _fold(source) == folded:
            return source
        for code in other_languages:
            # 지연 번역은 override 밖에서 평가되면 활성 언어로 풀리므로 즉시 번역한다.
            with translation.override(code):
                if _fold(gettext(source)) == folded:
                    return source
    return value


def _label_for_source(value: str, sources: tuple[str, ...]) -> str:
    return gettext(value) if value in sources else value


def normalize_personal_category(value: str) -> str:
    return _normalize_to_source(value, _PERSONAL_ENTRY_CATEGORY_SOURCE)


def personal_category_label(value: str) -> str:
    return _label_for_source(value, _PERSONAL_ENTRY_CATEGORY_SOURCE)


def normalize_collection_item_type(value: str) -> str:
    return _normalize_to_source(value, COLLECTION_ITEM_TYPE_SOURCE_LABELS)


def collection_item_type_label(value: str) -> str:
    return _label_for_source(value, COLLECTION_ITEM_TYPE_SOURCE_LABELS)
