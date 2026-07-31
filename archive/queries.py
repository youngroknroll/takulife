"""archive 도메인의 읽기 계층.

사용자 상태·관심·방문 기록을 위한 재사용 가능한 조회 로직. 조회·집계
로직은 뷰 계층이 아니라 여기 둔다(drafts/queries.py와 같은 방식).
"""
from django.db.models import Count, Exists, Min, OuterRef, Q, Subquery
from django.utils import timezone

from events.models import Event

from .models import (
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
