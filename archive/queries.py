"""archive 도메인의 읽기 계층.

사용자 상태·관심·방문 기록을 위한 재사용 가능한 조회 로직. 조회·집계
로직은 뷰 계층이 아니라 여기 둔다(drafts/queries.py와 같은 방식).
"""
import calendar
from dataclasses import dataclass
# 별칭을 쓰는 이유(`from datetime import date`가 아님): 아래 dataclass
# 필드 중 하나도 이름이 `date`라서, `field: T = default` 형태는 클래스
# 본문 스코프에서 어노테이션 `T`를 평가하기 *전에* 기본값을 필드 이름에
# 먼저 바인딩한다. 별칭 없이 같은 이름으로 임포트하면 그 시점엔 이미
# `None`으로 재바인딩된 뒤라 자기 어노테이션이 자신을 참조하지 못한다.
from datetime import date as _date

from django.db.models import Count, Exists, Max, Min, OuterRef, Q, Subquery
from django.urls import reverse
from django.utils import timezone

from events.models import Event

from .models import (
    ActivityLogEntry,
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)

# archive 상태 슬러그의 정본. 모델 자신의 choices에서 가져와 단일 출처를
# 유지한다. "interested"는 이제 EventInterest로 분리되어 제외된다.
ARCHIVE_STATUS_SLUGS: tuple[str, ...] = tuple(UserEventStatus.Status.values)

# archive SSR 목록 페이지(core.views가 렌더링)의 페이지 크기. 이 값이
# 제한하는 목록 쿼리 옆에 둔다(events.queries.PUBLIC_LISTING_PAGE_SIZE와
# 같은 방식).
ARCHIVE_RECORD_PAGE_SIZE = 10  # 기록장 (/archive/) — 저장한 이벤트
ARCHIVE_STATUS_PAGE_SIZE = 5  # 예정 목록 (/archive/statuses/)
ARCHIVE_VISIT_PAGE_SIZE = 5  # 방문 기록 (/archive/visits/)
ARCHIVE_PERSONAL_PAGE_SIZE = 5  # 비공식 목록 (/archive/personal/)
ARCHIVE_COLLECTION_PAGE_SIZE = 10  # 컬렉션 목록 (/collection/)
ARCHIVE_INTEREST_PAGE_SIZE = 10  # 찜 목록 (/archive/interests/)

# list_user_interests용 정렬 슬러그 -> order_by 필드. ""(기본값)는 기존
# -id 정렬(최근 찜순)이며, .get(sort, ARCHIVE_INTEREST_SORT_ORDERING[""])
# 이 기본값의 단일 출처가 되도록 여기 명시적으로 넣어둔다(값을 중복
# 리터럴로 두지 않기 위해 — ARCHIVE_VISIT_SORT_ORDERING과 같은 방식).
ARCHIVE_INTEREST_SORT_ORDERING: dict[str, str] = {
    "": "-id",
    "oldest": "id",
}

# list_user_statuses용 정렬 슬러그 -> order_by 필드. ""(기본값)는 기존
# -updated_at 정렬이며, 여기엔 일부러 "" 항목을 넣지 않았다 — 알 수 없는
# 슬러그는 .get(sort, default)의 기본값 인자만으로 자연히 떨어진다.
# UserEventStatus에 실제 컬럼이 있는 축만 제공한다 — event.start_date
# 같은 테이블을 넘나드는 축은 annotate가 필요해 범위 밖이다.
ARCHIVE_STATUS_SORT_ORDERING: dict[str, str] = {
    "created_at": "-created_at",
}

# list_user_visit_records용 정렬 슬러그 -> order_by 튜플. ""(기본값)는
# 기존 -visited_on, -id 정렬이며, 위 ARCHIVE_STATUS_SORT_ORDERING과
# 달리 여기엔 명시적으로 넣어서 .get(sort, ARCHIVE_VISIT_SORT_ORDERING[""])
# 이 기본값의 단일 출처가 되게 한다(값을 중복 리터럴로 두지 않기 위해).
ARCHIVE_VISIT_SORT_ORDERING: dict[str, tuple[str, str]] = {
    "": ("-visited_on", "-id"),
    "oldest": ("visited_on", "id"),
}

# list_user_personal_entries용 정렬 슬러그 -> order_by 튜플.
# ARCHIVE_VISIT_SORT_ORDERING과 완전히 같은 형태다: ""(기본값)는 기존
# -created_at, -id 정렬이며, .get(sort, ARCHIVE_PERSONAL_SORT_ORDERING[""])
# 이 기본값의 단일 출처가 되도록 명시적으로 넣어둔다.
ARCHIVE_PERSONAL_SORT_ORDERING: dict[str, tuple[str, str]] = {
    "": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
}


def user_status_counts(user, *, today=None) -> dict:
    """사용자의 archive 상태별 개수를 반환한다.

    자동 놓침 계산을 반영한 *파생* 상태 기준으로 센다. 그래서 진행이
    끝난 예정 행은 'planned'가 아니라 'missed'로 집계된다. 단일 집계
    쿼리이며, 개수가 0이어도 모든 정본 상태 슬러그가 결과에 포함된다.
    """
    if today is None:
        today = timezone.localdate()
    rows = (
        UserEventStatus.objects.filter(user=user)
        .with_derived_status(today=today)
        .values("derived_status")
        .annotate(count=Count("id"))
    )
    counts = {row["derived_status"]: row["count"] for row in rows}
    return {slug: counts.get(slug, 0) for slug in ARCHIVE_STATUS_SLUGS}


def list_user_statuses(user, status: str = "", *, q: str = "", sort: str = "", today=None):
    """사용자의 archive 상태를 최신순으로 반환한다(선택적 필터 적용).

    필터링과 행의 실효 상태 모두 *파생* 상태 계산을 사용한다. 그래서
    놓침 필터는 자동 놓침 행을 포함하고, 방문 예정 필터는 그것들을
    제외한다. 렌더링 중 행별 추가 쿼리가 나가지 않도록 event를 함께
    조회한다.

    ``q``는 event나 personal_entry의 제목/장소가 검색어를 포함하는
    행으로 결과를 좁힌다(대소문자 무시). 사용자 필터를 항상 먼저 적용해
    다른 사용자 데이터가 섞이지 않는다.

    ``sort``는 ARCHIVE_STATUS_SORT_ORDERING으로 정렬을 고른다. 알 수
    없거나 빈 값이면 오류를 내거나 빈 결과를 주지 않고 기본 -updated_at
    정렬로 떨어진다.
    """
    if today is None:
        today = timezone.localdate()
    ordering = ARCHIVE_STATUS_SORT_ORDERING.get(sort, "-updated_at")
    # AND가 아니라 OR인 이유: 상태 행의 대상은 event/personal_entry 중
    # 정확히 하나뿐이고 나머지는 항상 NULL이다(아래
    # list_user_unrecorded_visited_statuses의 same_subject Exists 필터도
    # 같은 NULL=NULL 함정을 AND로 겪었다). 정렬은
    # list_user_visit_records의 정본 -visited_on, -id와 같게 둬서,
    # 여기서 고른 "최근 방문"이 그 목록이 맨 위에 보여줄 행과 같아지게
    # 한다.
    latest_visit = VisitRecord.objects.filter(
        Q(event=OuterRef("event")) | Q(personal_entry=OuterRef("personal_entry")),
        user=OuterRef("user"),
    ).order_by("-visited_on", "-id")
    queryset = (
        UserEventStatus.objects.filter(user=user)
        .with_derived_status(today=today)
        .select_related("event", "personal_entry")
        .annotate(
            visit_record_id=Subquery(latest_visit.values("id")[:1]),
            review_text=Subquery(latest_visit.values("short_review")[:1]),
        )
        .order_by(ordering)
    )
    if status:
        queryset = queryset.filter(derived_status=status)
    if q:
        queryset = queryset.filter(
            Q(event__title__icontains=q)
            | Q(event__location_name__icontains=q)
            | Q(personal_entry__title__icontains=q)
            | Q(personal_entry__location_name__icontains=q)
        )
    return queryset


def list_user_unrecorded_visited_statuses(user):
    """방문 처리는 됐지만 아직 방문 기록이 없는 사용자의 상태 행을
    반환한다 — 컬렉션 우선 홈의 "미완성 기록" 영역용이다.

    visited는 파생 계산 값이 아니므로 저장된 원본 상태를 그대로 쓴다
    (with_derived_status 미사용). Exists 서브쿼리는 event와
    personal_entry 매칭을 AND가 아니라 OR로 묶어야 한다: 상태 행의
    대상은 둘 중 정확히 하나뿐이고 나머지는 항상 NULL이라, AND로
    묶으면 모든 행에서 OuterRef("event") 또는
    OuterRef("personal_entry")를 NULL과 비교하게 되어 항상 거짓이
    나온다 — 그러면 방문 기록이 이미 있어도 personal_entry 대상은
    영원히 미기록으로 조용히 취급돼 버린다.
    """
    same_subject = VisitRecord.objects.filter(
        Q(event=OuterRef("event")) | Q(personal_entry=OuterRef("personal_entry")),
        user=OuterRef("user"),
    )
    return (
        UserEventStatus.objects.filter(user=user, status=UserEventStatus.Status.VISITED)
        .select_related("event", "personal_entry")
        .annotate(has_record=Exists(same_subject))
        .filter(has_record=False)
        .order_by("-updated_at")
    )


def list_user_interests(user, *, q: str = "", sort: str = ""):
    """사용자의 관심(찜) 목록을 event/personal_entry와 함께 반환한다.

    렌더링 중 행별 추가 쿼리가 나가지 않도록 대상을 함께 조회한다.

    ``q``는 event나 personal_entry의 제목/장소가 검색어를 포함하는
    행으로 결과를 좁힌다(대소문자 무시, list_user_statuses와 같은 방식).

    ``sort``는 ARCHIVE_INTEREST_SORT_ORDERING으로 정렬을 고른다. 알 수
    없거나 빈 값이면 오류를 내거나 빈 결과를 주지 않고 기본 -id(최근
    찜순) 정렬로 떨어진다.
    """
    queryset = (
        EventInterest.objects.filter(user=user)
        .select_related("event", "personal_entry")
        .order_by(
            ARCHIVE_INTEREST_SORT_ORDERING.get(sort, ARCHIVE_INTEREST_SORT_ORDERING[""])
        )
    )
    if q:
        queryset = queryset.filter(
            Q(event__title__icontains=q)
            | Q(event__location_name__icontains=q)
            | Q(personal_entry__title__icontains=q)
            | Q(personal_entry__location_name__icontains=q)
        )
    return queryset


def user_interest_summary_counts(user, *, today=None) -> dict:
    """찜 목록 페이지 상단 카드용 요약 개수를 반환한다.

    ``interest_count`` — 전체 찜 행 수(공식+비공식).

    ``ongoing_count`` — 행사 기간이 현재 진행 중인 공식(event 연결) 찜
    수다. 양 끝 날짜와 마감임박 구간을 모두 포함한다(start_date <=
    today <= end_date). 화면에 보이는 행 상태 필터와 일치시킨 것이다
    (events/presenters.derive_event_display의 ongoing/closing_soon 상태
    모두 화면엔 "진행 중"으로 표시되므로, 상단 숫자와 행별 상태 배지가
    어긋나지 않는다).

    ``planned_overlap_count`` — 연결된 event에 대해 이 사용자의
    UserEventStatus *파생* 상태(archive/querysets.with_derived_status)가
    "planned"인 공식 찜 수다. 저장된 원본 값이 아니라 파생 상태를 쓰는
    이유는, 저장 컬럼은 여전히 "planned"라고 적혀 있어도 실제로는
    종료됐고 되돌리지 않았고 방문 기록도 없어 자동으로 "missed"가 된
    행을 제외하기 위해서다.

    두 event 기준 개수 모두 비공식(personal_entry 연결) 찜은 제외한다 —
    PersonalEntry는 진행 기간이 없고 상태 대상이 될 수도 없다.
    """
    if today is None:
        today = timezone.localdate()

    interest_count = EventInterest.objects.filter(user=user).count()

    ongoing_count = EventInterest.objects.filter(
        user=user,
        event__isnull=False,
        event__start_date__lte=today,
        event__end_date__gte=today,
    ).count()

    planned_event_ids = (
        UserEventStatus.objects.filter(user=user, event__isnull=False)
        .with_derived_status(today=today)
        .filter(derived_status="planned")
        .values_list("event_id", flat=True)
    )
    planned_overlap_count = EventInterest.objects.filter(
        user=user, event__isnull=False, event_id__in=planned_event_ids
    ).count()

    return {
        "interest_count": interest_count,
        "ongoing_count": ongoing_count,
        "planned_overlap_count": planned_overlap_count,
    }


def user_interest_event_ids(user, event_ids=None) -> dict:
    """주어진 사용자에 대해 {event_id: interest_id} 딕셔너리를 반환한다.

    ``event_ids``가 주어지면 그 id 목록으로 결과를 한정한다(페이지네이션
    목록 페이지에서 호출할 때 전체 테이블 스캔을 피하기 위해서다).
    """
    queryset = EventInterest.objects.filter(user=user)
    if event_ids is not None:
        queryset = queryset.filter(event_id__in=event_ids)
    return {row["event_id"]: row["id"] for row in queryset.values("event_id", "id")}


def user_interest_count(user) -> int:
    """주어진 사용자의 전체 이벤트 관심(찜) 수를 반환한다."""
    return EventInterest.objects.filter(user=user).count()


def list_user_planned_events(user):
    """사용자가 방문 예정으로 등록한(저장된 원본 'planned') 게시 행사를
    반환한다.

    방문 기록을 추가할 때 선택 가능한 대상 목록이다 — 가려고 했던
    행사에 방문을 기록하는 것이니까. 자동 놓침 파생 계산이 아니라 저장된
    원본 'planned' 상태를 쓰므로, 기간이 이미 끝난 행사도 뒤늦은 방문
    기록을 위해 여전히 선택할 수 있다. 제목순으로 정렬한다.
    """
    return (
        Event.objects.published()
        .filter(
            archive_user_statuses__user=user,
            archive_user_statuses__status=UserEventStatus.Status.PLANNED,
        )
        .order_by("title")
    )


def list_user_upcoming_planned_events(user, *, today=None):
    """사용자가 방문 예정으로 등록했지만 아직 시작하지 않은 게시 행사를
    가까운 순으로 반환한다.

    list_user_planned_events와 두 가지가 다르다: start_date가 오늘보다
    엄격히 이후인 것만 필터링하고(오늘이나 그 이전에 시작하는 예정
    행사는 "다가오는" 것이 아니다), 제목이 아니라 start_date로 정렬해
    가장 가까운 행사가 먼저 나온다 — 이건 방문 기록 선택 목록이 아니라
    컬렉션 우선 홈의 "다가오는 예정 이벤트" 영역용이다.
    """
    if today is None:
        today = timezone.localdate()
    return (
        Event.objects.published()
        .filter(
            archive_user_statuses__user=user,
            archive_user_statuses__status=UserEventStatus.Status.PLANNED,
            start_date__gt=today,
        )
        .order_by("start_date")
    )


def list_user_personal_entries(user, kind=None, *, q: str = "", sort: str = ""):
    """사용자 소유의 비공식 항목을 최신순으로 반환한다(kind로 선택
    필터링 가능).

    ``q``는 title/category/location_name/work_title/memo 중 하나가
    검색어를 포함하는 행으로 결과를 좁힌다(대소문자 무시).

    ``sort``는 ARCHIVE_PERSONAL_SORT_ORDERING으로 정렬을 고른다. 알 수
    없거나 빈 값이면 오류를 내거나 빈 결과를 주지 않고 기본
    -created_at, -id 정렬로 떨어진다.
    """
    queryset = PersonalEntry.objects.filter(user=user).order_by(
        *ARCHIVE_PERSONAL_SORT_ORDERING.get(sort, ARCHIVE_PERSONAL_SORT_ORDERING[""])
    )
    if kind:
        queryset = queryset.filter(kind=kind)
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(category__icontains=q)
            | Q(location_name__icontains=q)
            | Q(work_title__icontains=q)
            | Q(memo__icontains=q)
        )
    return queryset


def user_personal_entry_counts(user) -> dict:
    """사용자의 비공식(personal) 항목 요약 개수를 반환한다.

    archive/personal/ 페이지 요약 카드와 마이페이지 컬렉션 개수에서
    쓴다.

    ``visit_linked_count``는 방문 기록이 하나라도 연결된 PersonalEntry
    행 수다(distinct — 방문 기록이 여러 개인 항목도 한 번만 센다).
    personal_entry FK로만 필터링하므로 공식 Event 방문은 이 수에
    전혀 영향을 주지 않는다.
    """
    queryset = PersonalEntry.objects.filter(user=user)
    return {
        "total_count": queryset.count(),
        "visit_linked_count": queryset.filter(
            archive_user_visit_records__isnull=False
        )
        .distinct()
        .count(),
    }


def user_personal_interest_ids(user) -> dict:
    """사용자의 비공식 찜에 대해 {personal_entry_id: interest_id}를
    반환한다.

    비공식 페이지의 찜 토글 상태를 결정한다 — 각 카드가 이미 찜했는지,
    찜을 해제할 때 지울 interest id가 무엇인지 알 수 있다.
    """
    return {
        row["personal_entry_id"]: row["id"]
        for row in EventInterest.objects.filter(
            user=user,
            personal_entry__isnull=False,
            personal_entry__kind=PersonalEntry.Kind.PLACE,
        ).values("personal_entry_id", "id")
    }


def user_personal_statuses(user) -> dict:
    """비공식 상태에 대해 {personal_entry_id: (status_slug, status_id)}를
    반환한다.

    저장된 원본 상태를 그대로 쓴다 — 비공식 항목은 진행 기간이 없어서
    자동 놓침 계산이 애초에 적용되지 않는다.
    """
    return {
        row["personal_entry_id"]: (row["status"], row["id"])
        for row in UserEventStatus.objects.filter(
            user=user,
            personal_entry__isnull=False,
            personal_entry__kind=PersonalEntry.Kind.PLACE,
        ).values("personal_entry_id", "status", "id")
    }


def user_visit_record_counts(user) -> dict:
    """사용자의 방문 기록 요약 개수를 반환한다.

    필터링된 부분집합이 아니라 항상 사용자의 전체 방문 이력을 센다.
    그래야 archive/visits/ 페이지 요약 카드가 활성 필터/검색과 무관하게
    안정된 총계를 보여준다. ``memo_count``는 short_review가 비어있지
    않은 것만의 부분집합이다.
    """
    queryset = VisitRecord.objects.filter(user=user)
    return {
        "total_count": queryset.count(),
        "memo_count": queryset.exclude(short_review="").count(),
    }


def user_visit_record_photo_count(user) -> int:
    """주어진 사용자가 소유한 방문 기록 사진의 총 개수를 반환한다
    (계정 탈퇴 삭제 대상 요약에서 쓴다. user_visit_record_counts에
    합치지 않고 따로 둔 이유는 그 함수가 쿼리셋 하나에 집중하게 하기
    위해서다)."""
    return VisitRecordPhoto.objects.filter(visit_record__user=user).count()


def list_user_visit_records(
    user,
    *,
    official=None,
    category_codes=(),
    category_label: str = "",
    q: str = "",
    sort: str = "",
):
    """사용자의 방문 기록을 최신순으로, 연관 데이터를 미리 로드해
    반환한다.

    정본 정렬과 prefetch를 공유해 SSR 페이지와 API가 일관되게 유지된다
    (event·photos에서 N+1 쿼리를 피한다).

    ``official`` — True면 event 연결 기록만, False면 personal_entry
    기록만, None이면 제한 없음.

    ``category_codes`` / ``category_label`` — ``category_label``이 있으면
    event.category가 category_codes에 있거나 personal_entry.category가
    category_label과 같은 행으로 좁힌다(OR). label은 별도 조회 없이
    원본 그대로 비교하므로, 자유 텍스트 라벨로 저장된 비공식 항목도
    바로 매칭된다.

    ``q`` — title, location_name(양쪽 FK 모두), short_review에 대해
    대소문자 무시 포함 검색.

    ``sort``는 ARCHIVE_VISIT_SORT_ORDERING으로 정렬을 고른다. 알 수
    없거나 빈 값이면 오류를 내거나 빈 결과를 주지 않고 기본
    -visited_on, -id 정렬로 떨어진다.
    """
    queryset = (
        VisitRecord.objects.filter(user=user)
        .select_related("event", "personal_entry")
        .prefetch_related("photos")
        .order_by(*ARCHIVE_VISIT_SORT_ORDERING.get(sort, ARCHIVE_VISIT_SORT_ORDERING[""]))
    )
    if official is True:
        queryset = queryset.filter(event__isnull=False)
    elif official is False:
        queryset = queryset.filter(event__isnull=True)
    if category_label:
        queryset = queryset.filter(
            Q(event__category__in=category_codes)
            | Q(personal_entry__category=category_label)
        )
    if q:
        queryset = queryset.filter(
            Q(event__title__icontains=q)
            | Q(event__location_name__icontains=q)
            | Q(personal_entry__title__icontains=q)
            | Q(personal_entry__location_name__icontains=q)
            | Q(short_review__icontains=q)
        )
    return queryset


def list_user_collection_items(
    user,
    *,
    work_title: str = "",
    character_name: str = "",
    item_type: str = "",
    is_wanted=None,
    duplicate=None,
    tradeable=None,
    owned=None,
    q: str = "",
):
    """사용자 소유 컬렉션 항목을 최신순으로 반환한다(선택적 필터 적용).

    `work_title`/`character_name`/`item_type`은 정확히 일치하는 값으로
    거르는 필터다. `duplicate`, `tradeable`, `owned`는 저장된 필드가
    아니라 *파생* 필터다 — "duplicate"는 수량>=2, "tradeable"은
    교환가능수량>0, "owned"는 수량>0을 뜻한다(별도 duplicate_count
    필드는 의도적으로 두지 않았다).

    ``q``는 name/work_title/character_name/memo 중 하나가 검색어를
    포함하는 행으로 결과를 좁힌다(대소문자 무시,
    list_user_personal_entries의 q와 같은 방식). item_type은 의도적으로
    q 검색 대상에서 뺐다.
    """
    queryset = CollectionItem.objects.filter(user=user).order_by("-id")
    if work_title:
        queryset = queryset.filter(work_title=work_title)
    if character_name:
        queryset = queryset.filter(character_name=character_name)
    if item_type:
        queryset = queryset.filter(item_type=item_type)
    if is_wanted is not None:
        queryset = queryset.filter(is_wanted=is_wanted)
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(work_title__icontains=q)
            | Q(character_name__icontains=q)
            | Q(memo__icontains=q)
        )
    if duplicate is not None:
        if duplicate:
            queryset = queryset.filter(quantity__gte=2)
        else:
            queryset = queryset.filter(quantity__lt=2)
    if tradeable is not None:
        if tradeable:
            queryset = queryset.filter(tradeable_quantity__gt=0)
        else:
            queryset = queryset.filter(tradeable_quantity=0)
    if owned is not None:
        if owned:
            queryset = queryset.filter(quantity__gt=0)
        else:
            queryset = queryset.filter(quantity=0)
    return queryset


def user_collection_item_filter_values(user) -> dict:
    """사용자의 컬렉션 항목에서 쓰인 work_title/character_name/item_type
    값을 중복 없이 반환한다. 필터 위젯 옵션을 채우는 데 쓴다.

    아래 user_visit_category_values와 달리(그쪽은 호출자가
    core.vocab 라벨을 해석한 뒤에야 중복을 제거한다) work_title/
    character_name/item_type은 자유 텍스트로 저장되고 별도 어휘 해석
    단계가 없으므로, 중복 제거와 빈 값 제외를 뷰가 아니라 이 쿼리
    계층에서 바로 처리한다.

    각 목록을 명시적으로 정렬한다 — 호출자가 이 값을 그대로
    <select> 옵션으로 렌더링하는데, ORDER BY 없는 DISTINCT는 행 순서가
    정해져 있지 않기 때문이다.
    """
    fields = ("work_title", "character_name", "item_type")
    return {
        field: list(
            CollectionItem.objects.filter(user=user)
            .exclude(**{field: ""})
            .values_list(field, flat=True)
            .distinct()
            .order_by(field)
        )
        for field in fields
    }


def user_collection_item_summary_counts(user) -> dict:
    """사용자 컬렉션 항목 요약 개수를 반환한다(/collection/ 요약 카드용).

    owned, wanted, tradeable은 서로 독립된 세 축이지 하나를 셋으로
    나눈 게 아니다 — 한 행이 보유(owned)이면서 동시에 구함(wanted)일
    수 있고(예: 이미 있지만 하나 더 구하는 중인 중복 아이템),
    tradeable_quantity > 0은 둘 중 어느 쪽과도 결합할 수 있다. 한 행이
    owned_count / wanted_count / tradeable_count 여러 개에 동시에
    잡힐 수 있으므로 이 셋을 더한 값은 사용자의 전체 항목 수가 아니다
    — 절대 셋을 합산해 총계로 쓰지 말 것. total_count가 따로 있는
    이유가 바로 이거다: 세 축 어디에도 속하지 않아도(수량=0,
    구함=False, 교환가능수량=0이어도 등록된 항목이라면) 무조건 세는
    유일하게 믿을 수 있는 "이 사용자가 컬렉션 항목을 가지고 있는가"
    수치다.

    - owned_count: 수량>0인 행(실제로 보유 중)이며 is_wanted나
      tradeable_quantity와 무관하다.
    - wanted_count: is_wanted=True인 행이며 수량이나
      tradeable_quantity와 무관하다.
    - tradeable_count: tradeable_quantity>0인 행이며 수량이나
      is_wanted와 무관하다.
    - total_count: 세 축과 무관하게 사용자 소유 전체 행 수.
    """
    queryset = CollectionItem.objects.filter(user=user)
    return {
        "owned_count": queryset.filter(quantity__gt=0).count(),
        "wanted_count": queryset.filter(is_wanted=True).count(),
        "tradeable_count": queryset.filter(tradeable_quantity__gt=0).count(),
        "total_count": queryset.count(),
    }


def user_collection_item_work_title_facets(user) -> list:
    """사용자 컬렉션 항목의 {"work_title", "count", "first_id"} 집계를
    반환한다(빈 work_title 제외, 소유자 한정).

    개수 내림차순, 동점이면 work_title 오름차순으로 정렬한다 —
    user_collection_item_filter_values와 같은 이유로 명시적
    .order_by()를 쓴다: ORDER BY 없는 GROUP BY는 행 순서가 정해져
    있지 않으므로 동점 처리 기준을 암묵적으로 기대하지 않고 명시적으로
    요청해야 한다.

    first_id는 그 work_title에서 가장 먼저 등록된 항목의 id다
    (Min("id")). 호출자는 이 값으로 집계를 등록순으로 다시 정렬해
    시리즈별 색상 팔레트를 정한다 — 화면 표시 순서(개수 내림차순)와
    팔레트 순서(먼저 등록된 순)는 의도적으로 다르다. 개수 순서로
    색을 정하면 항목이 하나 추가될 때마다 순위가 바뀌어 기존
    work_title의 색이 계속 흔들리지만, 최초 등록 순서로 정하면 한
    work_title의 색이 평생 안정적으로 유지된다.
    """
    return list(
        CollectionItem.objects.filter(user=user)
        .exclude(work_title="")
        .values("work_title")
        .annotate(count=Count("id"), first_id=Min("id"))
        .order_by("-count", "work_title")
        .values("work_title", "count", "first_id")
    )


def list_items_acquired_at_visit(visit):
    """하나의 VisitRecord에 연결된 CollectionItem을 등록순으로 반환한다
    — 방문 기록 상세 페이지 "이 방문에서 얻은 굿즈" 영역용이다.

    역방향 FK(CollectionItem.visit_record)를 쓰므로 archive 내부
    쿼리이며 새로운 도메인 간 결합이 생기지 않는다.
    """
    return list(visit.archive_collection_items.all().order_by("id"))


def list_visit_records_for_personal_entry(entry):
    """하나의 PersonalEntry에 연결된 VisitRecord를 최신순으로 반환한다
    — 비공식 장소 상세 페이지 "이 장소의 방문 기록" 영역용이다.

    list_user_visit_records에 인자를 추가하는 대신 전용 함수로 분리했다:
    그 함수는 이미 소비자가 둘이라, 상세 페이지 하나만을 위한 매개변수를
    더하면 둘 다 영향을 받는다. 여기엔 `user` 필터를 따로 걸지 않는다
    (list_items_acquired_at_visit와 같은 방식) — 호출자의
    get_object_or_404(..., user=request.user)가 이미 `entry`를 소유자로
    한정했고, 어떤 쓰기 경로도 다른 사용자의 방문을 여기에 붙일 수
    없다.
    """
    return list(entry.archive_user_visit_records.all().order_by("-visited_on", "-id"))


def user_visit_category_values(user):
    """사용자 방문 기록의 (event__category, personal_entry__category) 쌍을
    반환한다.

    방문 타임라인과 맞춰 최신순으로 정렬한다. 뷰는 이 쌍들로 전체 모델
    인스턴스를 로드하거나 현재 페이지로 제한하지 않고 카테고리 칩
    전체 집합을 뽑아낸다.
    """
    return (
        VisitRecord.objects.filter(user=user)
        .order_by("-visited_on", "-id")
        .values_list("event__category", "personal_entry__category")
    )


# ---------------------------------------------------------------------------
# 개인 활동 달력 월별 조회. 5개의 읽기 소스를 하나의 평평한 달력 항목
# 목록으로 합치며, 언제나 사용자로 먼저 한정한다:
#
#   schedule ("일정")       — 예정 상태인 UserEventStatus 행. 연결된
#                             event의 전체 기간(start..end, 양끝 포함)
#   visit ("방문")           — VisitRecord.visited_on
#   goods_acquired ("굿즈")  — CollectionItem.acquired_on, 없으면
#                             created_at의 로컬 날짜로 대체
#   <ActivityLogEntry.Kind> — 추가만 되는 행동 이력. occurred_at의
#                             로컬 날짜로 표시
#   <ActivityLogEntry.Kind.INTEREST_ADDED> 대체 경로 — 대응하는 로그
#                             행이 없는, 아직 남아있는 EventInterest
#                             (서비스 출시 전 만들어진 옛 찜이라 소급
#                             기록을 하지 않는다 — 이 대체 경로는 로그
#                             행이 이미 그 찜을 포함하지 않을 때만
#                             쓰여, 둘이 같은 찜을 중복으로 세지 않는다)
#
# 소스마다 쿼리 하나씩이다. "대체 값이 있는 사실 날짜" 소스 둘(굿즈,
# 찜)의 날짜 계산과 월 구간 필터링은 파이썬에서 처리한다. 대체 로직을
# 필드 조회 하나로 표현할 수 없기 때문이다 — 현재 사용자당 행 수
# 규모에서는 별도 집계 테이블 없이도 괜찮다.
# ---------------------------------------------------------------------------

SCHEDULE_KIND = "schedule"
VISIT_KIND = "visit"
GOODS_ACQUIRED_KIND = "goods_acquired"


@dataclass(frozen=True)
class CalendarActivityItem:
    """달력에 표시할 활동 한 행. 단일 사실-날짜 항목(방문/굿즈 획득/
    행동성 활동)은 `date`를 채우고 `start`/`end`는 None으로 둔다. 기간
    항목(일정)은 `start`/`end`(양끝 포함)를 채우고 `date`는 None으로
    둔다.

    `label`/`url`/`time_text`는 웹 화면 표시용 필드다(새 비즈니스
    규칙이 아니다. 아래 각 비공개 헬퍼가 생성 시점에 이미 갖고 있는
    원본 객체에서 값을 채운다):
    - `label`: 대상의 표시 이름(event 제목 / CollectionItem.name /
      ActivityLogEntry.subject_label — 원본 행이 삭제돼도 남는 스냅샷).
    - `url`: 연결된 수정/상세 화면(event 상세, 방문 기록 수정, 컬렉션
      항목 수정)이며, 대상이 이미 삭제된 SET_NULL ActivityLogEntry인
      경우엔 `None`이다(그 경우 `subject_label`만 남고 연결할 대상이
      없다).
    - `time_text`: ActivityLogEntry.occurred_at에서만 나오는 행동
      시각의 로컬 "HH:MM"이다. 다른 소스는 시각을 보여줄 게 없어서
      (VisitRecord.visited_on과 CollectionItem의 날짜 필드는 단순
      날짜이고, 기간 항목은 날짜 범위다) 이 값을 ""로 둔다.
    """

    kind: str
    date: _date | None = None
    start: _date | None = None
    end: _date | None = None
    label: str = ""
    url: str | None = None
    time_text: str = ""


def _calendar_month_bounds(year, month):
    month_start = _date(year, month, 1)
    month_end = _date(year, month, calendar.monthrange(year, month)[1])
    return month_start, month_end


def _schedule_items(user, month_start, month_end):
    """연결된 event의 진행 기간이 이 달과 겹치는 예정 상태 행을
    반환한다 — events.querysets.EventQuerySet.overlapping_month의 경계
    규칙을, Event.objects를 직접 쓰는 대신 event FK를 통해 적용한
    것이다."""
    statuses = (
        UserEventStatus.objects.filter(
            user=user,
            status=UserEventStatus.Status.PLANNED,
            event__isnull=False,
            event__start_date__isnull=False,
            event__start_date__lte=month_end,
        )
        .filter(
            Q(event__end_date__isnull=True, event__start_date__gte=month_start)
            | Q(event__end_date__isnull=False, event__end_date__gte=month_start)
        )
        .select_related("event")
    )
    return [
        CalendarActivityItem(
            kind=SCHEDULE_KIND,
            start=status.event.start_date,
            end=status.event.end_date or status.event.start_date,
            label=status.event.title,
            url=reverse("event-detail-page", args=[status.event_id]),
        )
        for status in statuses
    ]


def _visit_items(user, month_start, month_end):
    visits = VisitRecord.objects.filter(
        user=user, visited_on__gte=month_start, visited_on__lte=month_end
    ).select_related("event", "personal_entry")
    return [
        CalendarActivityItem(
            kind=VISIT_KIND,
            date=visit.visited_on,
            label=visit.event.title if visit.event_id else visit.personal_entry.title,
            url=reverse("archive-visit-edit-page", args=[visit.id]),
        )
        for visit in visits
    ]


def _goods_acquired_items(user, month_start, month_end):
    items = []
    for item in CollectionItem.objects.filter(user=user):
        display_date = item.acquired_on or timezone.localdate(item.created_at)
        if month_start <= display_date <= month_end:
            items.append(
                CalendarActivityItem(
                    kind=GOODS_ACQUIRED_KIND,
                    date=display_date,
                    label=item.name,
                    url=reverse("collection-edit-page", args=[item.id]),
                )
            )
    return items


def _log_entry_items(user, month_start, month_end):
    """ActivityLogEntry는 대상 행이 사라진 뒤에도 이 소스가 라벨을
    유지할 수 있도록 durable한 `subject_label` 스냅샷을 갖고 있다
    (event/visit_record/collection_item은 대상이 삭제되면 모두
    SET_NULL된다, archive/models.py). 그 경우 연결할 대상이 없으므로
    `url`은 `None`으로 낮아진다."""
    entries = ActivityLogEntry.objects.filter(
        user=user,
        occurred_at__date__gte=month_start,
        occurred_at__date__lte=month_end,
    )
    items = []
    for entry in entries:
        if entry.event_id:
            url = reverse("event-detail-page", args=[entry.event_id])
        elif entry.visit_record_id:
            url = reverse("archive-visit-edit-page", args=[entry.visit_record_id])
        elif entry.collection_item_id:
            url = reverse("collection-edit-page", args=[entry.collection_item_id])
        else:
            url = None
        # aware datetime에서(여기선 USE_TZ=True)
        # timezone.localdate(entry.occurred_at)는
        # timezone.localtime(entry.occurred_at).date()와 같은 값이다 —
        # time_text도 만들어내는 같은 localtime 값에서 뽑아낸 것일
        # 뿐이라 표시되는 날짜 자체는 이 필드를 추가하기 전과 동일하다.
        local_dt = timezone.localtime(entry.occurred_at)
        items.append(
            CalendarActivityItem(
                kind=entry.kind,
                date=local_dt.date(),
                label=entry.subject_label,
                url=url,
                time_text=local_dt.strftime("%H:%M"),
            )
        )
    return items


def _interest_added_fallback_items(user, month_start, month_end):
    """소급 기록을 하지 않기로 한 대체 경로: 대응하는 interest_added
    로그 행이 없는, 아직 남아있는 EventInterest다(ActivityLogEntry가
    생기기 전의 옛 데이터). 이미 실제 로그 행이 있는 event는 제외해,
    서비스 출시 이후 찜이 중복으로 세지 않는다."""
    logged_event_ids = set(
        ActivityLogEntry.objects.filter(
            user=user,
            kind=ActivityLogEntry.Kind.INTEREST_ADDED,
            event__isnull=False,
        ).values_list("event_id", flat=True)
    )
    interests = EventInterest.objects.filter(user=user, event__isnull=False).exclude(
        event_id__in=logged_event_ids
    ).select_related("event")
    items = []
    for interest in interests:
        display_date = timezone.localdate(interest.created_at)
        if month_start <= display_date <= month_end:
            items.append(
                CalendarActivityItem(
                    kind=ActivityLogEntry.Kind.INTEREST_ADDED,
                    date=display_date,
                    label=interest.event.title,
                    url=reverse("event-detail-page", args=[interest.event_id]),
                )
            )
    return items


def list_user_activity_for_month(user, *, year, month, kinds=None):
    """사용자의 한 달치 달력 표시용 활동을 CalendarActivityItem의 평평한
    목록으로 반환한다. 언제나 `user`로 먼저 한정한다.

    `kinds`가 주어지면 그 kind 문자열 부분집합(SCHEDULE_KIND,
    VISIT_KIND, GOODS_ACQUIRED_KIND 또는 ActivityLogEntry.Kind 값)으로
    결과를 좁힌다.
    """
    month_start, month_end = _calendar_month_bounds(year, month)

    items = (
        _schedule_items(user, month_start, month_end)
        + _visit_items(user, month_start, month_end)
        + _goods_acquired_items(user, month_start, month_end)
        + _log_entry_items(user, month_start, month_end)
        + _interest_added_fallback_items(user, month_start, month_end)
    )

    if kinds is not None:
        allowed = set(kinds)
        items = [item for item in items if item.kind in allowed]

    return items


def _latest_schedule_match_date(user, q, kinds):
    """event 제목이 `q`와 일치하는 PLANNED 상태 중 가장 늦은 .start —
    _schedule_items의 (kind, label, date) 규칙을 그대로 따르되, 파이썬
    으로 모든 행을 만들어 비교하지 않고 DB에서 제목으로 필터링한다."""
    if kinds is not None and SCHEDULE_KIND not in kinds:
        return None
    return UserEventStatus.objects.filter(
        user=user,
        status=UserEventStatus.Status.PLANNED,
        event__isnull=False,
        event__title__icontains=q,
    ).aggregate(latest=Max("event__start_date"))["latest"]


def _latest_visit_match_date(user, q, kinds):
    """event 또는 personal_entry 제목이 `q`와 일치하는 방문 중 가장
    늦은 visited_on — _visit_items가 라벨을 정하는 방식(연결됐으면
    event 제목, 아니면 personal_entry 제목)을 그대로 따른다."""
    if kinds is not None and VISIT_KIND not in kinds:
        return None
    return (
        VisitRecord.objects.filter(user=user)
        .filter(Q(event__title__icontains=q) | Q(personal_entry__title__icontains=q))
        .aggregate(latest=Max("visited_on"))["latest"]
    )


def _latest_goods_match_date(user, q, kinds):
    """name이 `q`와 일치하는 CollectionItem 중 가장 늦은 파생 표시
    날짜(acquired_on 또는 created_at의 로컬 날짜). 표시 날짜는 단순
    컬럼이 아니라 파생 값이라 DB에서 집계할 수 없다 — 다만 행 집합
    자체는 이미 name__icontains로 좁혀져 있어서, 사용자의 전체
    컬렉션이 아니라 실제로 일치하는 작은 집합만 파이썬으로 가져와
    최댓값을 고른다."""
    if kinds is not None and GOODS_ACQUIRED_KIND not in kinds:
        return None
    match_dates = [
        item.acquired_on or timezone.localdate(item.created_at)
        for item in CollectionItem.objects.filter(user=user, name__icontains=q)
    ]
    return max(match_dates) if match_dates else None


def _latest_log_entry_match_date(user, q, kinds):
    """subject_label이 `q`와 일치하는 ActivityLogEntry 중 가장 늦은
    로컬 표시 날짜. `kinds`가 있으면 먼저 그걸로 좁힌다(DB의
    kind__in 필터로, list_user_activity_for_month의 파이썬 쪽 kind
    필터와 같은 효과). occurred_at -> 로컬 날짜는 파생 값이라
    (timezone.localtime(...).date(), _log_entry_items와 동일) 이미
    일치한 행에 대해서만 파이썬에서 계산한다."""
    entries = ActivityLogEntry.objects.filter(user=user, subject_label__icontains=q)
    if kinds is not None:
        entries = entries.filter(kind__in=kinds)
    match_dates = [
        timezone.localtime(occurred_at).date()
        for occurred_at in entries.values_list("occurred_at", flat=True)
    ]
    return max(match_dates) if match_dates else None


def _latest_interest_fallback_match_date(user, q, kinds):
    """소급 기록을 하지 않는 대체 경로에서, event 제목이 `q`와 일치하는
    아직 남아있는 EventInterest 중 가장 늦은 파생 표시 날짜
    (created_at의 로컬 날짜). 이미 실제 interest_added 로그 행이 있는
    event는 제외한다 — _interest_added_fallback_items와 완전히 같은
    로직이며, DB에서 제목으로 먼저 좁힌다는 점만 다르다."""
    if kinds is not None and ActivityLogEntry.Kind.INTEREST_ADDED not in kinds:
        return None
    logged_event_ids = set(
        ActivityLogEntry.objects.filter(
            user=user,
            kind=ActivityLogEntry.Kind.INTEREST_ADDED,
            event__isnull=False,
        ).values_list("event_id", flat=True)
    )
    created_ats = (
        EventInterest.objects.filter(user=user, event__isnull=False, event__title__icontains=q)
        .exclude(event_id__in=logged_event_ids)
        .values_list("created_at", flat=True)
    )
    match_dates = [timezone.localdate(created_at) for created_at in created_ats]
    return max(match_dates) if match_dates else None


def find_latest_activity_date_for_query(user, q, *, kinds=None):
    """`user`의 활동 항목 중 라벨이 `q`를 포함하는(대소문자 무시) 가장
    최근 달력 날짜를 반환한다. 일치하는 게 없으면 None이다 — 활동
    달력의 날짜 이동 검색 기능의 읽기 쪽이다. `q`가 비어있거나 공백뿐
    이면 쿼리 없이 항상 None을 반환한다.

    한 달로 범위가 제한돼 소스별 파이썬 루프가 작게 유지되는
    list_user_activity_for_month와 달리, 이 함수의 날짜 범위는
    제한이 없다(전체 활동 이력) — 그래서 `q`와 라벨 비교를 사용자의
    전체 이력을 파이썬으로 만들어 거르는 대신 각 소스 자신의 DB
    쿼리로 밀어 넣는다(name/title/subject_label __icontains=q). 위 각
    소스별 헬퍼는 대응하는 list_user_activity_for_month 쪽 헬퍼와
    똑같은 (kind, label, date) 규칙을 따르며, `q`(와 `kinds`)로 DB에서
    먼저 좁힌다는 점만 다르다.

    이 함수의 유일한 호출자(core.views.activity_calendar)는 현재
    활성화된 type= 필터의 kinds를 그대로 넘긴다. 그래서 화면에서
    숨겨진 kind만 일치하는 날짜로는 이동하지 않는다.

    기간 항목(일정)은 화면에 표시되는 전체 범위로 일치 여부를
    판정하지만, 반환하는 날짜는 `.start`다 — 월 달력 그리드가 실제로
    그것을 처음 보여주는 날이다(list_user_activity_for_month가 기간
    항목을 날짜별로 나누는 방식과 같다).
    """
    q = q.strip()
    if not q:
        return None

    match_dates = [
        match_date
        for match_date in (
            _latest_schedule_match_date(user, q, kinds),
            _latest_visit_match_date(user, q, kinds),
            _latest_goods_match_date(user, q, kinds),
            _latest_log_entry_match_date(user, q, kinds),
            _latest_interest_fallback_match_date(user, q, kinds),
        )
        if match_date is not None
    ]
    return max(match_dates) if match_dates else None
