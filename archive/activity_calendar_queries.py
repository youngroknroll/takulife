"""archive 도메인의 개인 활동 달력 읽기 계층.

archive/queries.py(일반 아카이브 읽기 계층)에서 분리했다 — 이 모듈은 월별
달력 조회와 날짜 이동 검색만 다룬다(docs/backlog.md E2).
"""
import calendar
from dataclasses import dataclass
# 별칭을 쓰는 이유(`from datetime import date`가 아님): 아래 dataclass
# 필드 중 하나도 이름이 `date`라서, `field: T = default` 형태는 클래스
# 본문 스코프에서 어노테이션 `T`를 평가하기 *전에* 기본값을 필드 이름에
# 먼저 바인딩한다. 별칭 없이 같은 이름으로 임포트하면 그 시점엔 이미
# `None`으로 재바인딩된 뒤라 자기 어노테이션이 자신을 참조하지 못한다.
from datetime import date as _date

from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from .models import ActivityLogEntry, CollectionItem, EventInterest, UserEventStatus, VisitRecord

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

    이 함수의 유일한 호출자(web.views.activity_calendar)는 현재
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
