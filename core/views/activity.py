"""활동 달력(캘린더) 조회 및 필터 관련 뷰와 헬퍼 모음."""
import logging
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from archive.activity_calendar_queries import (
    GOODS_ACQUIRED_KIND,
    SCHEDULE_KIND,
    VISIT_KIND,
    find_latest_activity_date_for_query,
    list_user_activity_for_month,
)
from archive.models import ActivityLogEntry
from archive.queries import user_status_counts
from core.calendar_grid import month_grid

from ._helpers import _adjacent_month, _parse_calendar_date, _parse_calendar_month

logger = logging.getLogger(__name__)


# 사용자에게 보이는 5개 활동 그룹 -> 각각이 포괄하는
# archive.activity_calendar_queries kind 상수. "interest"는 옛 찜 대체 경로도
# 함께 포괄하는데,
# archive.activity_calendar_queries._interest_added_fallback_items가 별도 kind 문자열 없이
# ActivityLogEntry.Kind.INTEREST_ADDED를 그대로 재사용한다.
# "visit"과 "goods"는 상태 테이블(VisitRecord/CollectionItem)만 출처로
# 삼는다 — 방문·등록·수정 각 행동은 행동 로그에도 흔적을 남기는데, 그
# 로그까지 함께 세면 같은 활동이 두 번 보인다(중복 표시 결함 수정, 사용자
# 결정: 상태 테이블 우선).
_ACTIVITY_TYPE_GROUPS = {
    "schedule": [SCHEDULE_KIND],
    "interest": [ActivityLogEntry.Kind.INTEREST_ADDED, ActivityLogEntry.Kind.INTEREST_REMOVED],
    "status": [ActivityLogEntry.Kind.STATUS_CHANGED, ActivityLogEntry.Kind.STATUS_REMOVED],
    "visit": [VISIT_KIND],
    "goods": [GOODS_ACQUIRED_KIND],
}

_KIND_TO_ACTIVITY_TYPE_GROUP = {
    kind: group for group, kinds in _ACTIVITY_TYPE_GROUPS.items() for kind in kinds
}

# 실제로 달력 범례/셀 항목/선택 날짜 목록/카운트에 표시되는 4개 그룹.
# "status"는 옛 ?type= 북마크 호환을 위해 실재하는 매치 가능 그룹으로
# 남아 있고 _ACTIVITY_TYPE_GROUPS에도 항목이 있지만, 이 화면 어디에도
# 렌더링되거나 집계되지 않는다.
_VISIBLE_ACTIVITY_TYPE_GROUPS = ("schedule", "interest", "visit", "goods")


def _visible_activity_group(kind):
    """활동 kind를 표시 그룹으로 매핑한다. 그 kind가 달력 범례/셀 항목/선택
    날짜 목록/카운트 어디에도 절대 나타나면 안 되면 None을 반환한다 — 이
    네 소비처가 전부 이 한 지점을 거치므로 서로 조용히 어긋날 수 없다
    (상태만 있는 날의 aria-label 카운트는 실제 렌더링된 항목 수와
    반드시 일치해야 한다)."""
    group = _KIND_TO_ACTIVITY_TYPE_GROUP.get(kind)
    if group == "status":
        return None
    return group


def _parse_activity_type_filter(request):
    """5개 유효 그룹 중 하나인 ?type= 값들을 요청 순서대로, 중복 없이
    반환한다. 알 수 없는 값은 예외를 던지지 않고 조용히 무시한다
    (event_list의 기존 관행과 동일)."""
    selected = []
    seen = set()
    for raw_value in request.GET.getlist("type"):
        if raw_value in _ACTIVITY_TYPE_GROUPS and raw_value not in seen:
            seen.add(raw_value)
            selected.append(raw_value)
    return selected


def _activity_extra_query(selected_types):
    """이미 검증된 현재 type= 선택 값들을 '&type=...&type=...' 형태의
    쿼리스트링 꼬리로 반환한다 — _calendar_extra_query/_pager.html의
    extra_query와 같은 선행 '&' 관례를 따른다."""
    if not selected_types:
        return ""
    return "&" + urlencode([("type", value) for value in selected_types])


def _format_month_day(value):
    return f"{value.month}월 {value.day}일"


def _activity_filter_url(*, year, month, selected_date, types):
    """표시 중인 month/date를 보존하고 주어진 ?type= 선택을 담은 완전한
    /archive/calendar/ URL을 만든다 — 범례 링크는 토글이든 초기화든
    전부 이 함수를 거쳐 month/date가 절대 빠지지 않는다(날짜 이동 검색
    폼에서 얻은 숨은 input 교훈과 같은 이유)."""
    params = [("month", f"{year:04d}-{month:02d}")]
    if selected_date is not None:
        params.append(("date", selected_date.isoformat()))
    params += [("type", value) for value in types]
    return f"{reverse('archive-calendar-page')}?{urlencode(params)}"


def _activity_kind_filters(*, year, month, selected_date, selected_types, kind_counts):
    """보이는 4개 그룹을 클릭 가능한 범례 필터 항목으로 반환한다: 각각
    {group, count, is_active, toggle_url} 형태이며, toggle_url은 비활성
    상태면 현재 선택에 그룹을 더하고 활성 상태면 뺀다. `count`는 호출자가
    넘긴, 필터와 무관한 kind_counts에서 온다 — 여기서 필터링된 집합으로
    다시 계산하지 않는다."""
    filters = []
    for group in _VISIBLE_ACTIVITY_TYPE_GROUPS:
        is_active = group in selected_types
        if is_active:
            toggled_types = [value for value in selected_types if value != group]
        else:
            toggled_types = selected_types + [group]
        filters.append(
            {
                "group": group,
                "count": kind_counts[group],
                "is_active": is_active,
                "toggle_url": _activity_filter_url(
                    year=year, month=month, selected_date=selected_date, types=toggled_types
                ),
            }
        )
    return filters


def _build_selected_activity_items(items):
    """선택된 날짜의 archive.activity_calendar_queries.CalendarActivityItem
    행들을 상세 목록 표시용 dict({group, label, url, date_text})로 바꾼다.

    `label`/`url`은 CalendarActivityItem에서 그대로 가져온다
    (archive/activity_calendar_queries.py의 각 내부 헬퍼가 이미 들고 있는
    객체에서 채운다 — label은
    Event.title/CollectionItem.name/ActivityLogEntry.subject_label, url은
    event-detail/visit-edit/collection-edit의 reverse()이며 SET_NULL
    대상이 사라지면 `None`). `date_text`는 표시 전용 관심사라 여기서
    조립한다(`.date`/`.start`/`.end`로 날짜 단위 텍스트를 만들고, 시각이
    있는 항목엔 `.time_text`를 붙인다 — "7월 19일 14:32" 형태).
    """
    display_items = []
    for item in items:
        group = _visible_activity_group(item.kind)
        if group is None:
            continue
        if item.date is not None:
            date_text = _format_month_day(item.date)
            if item.time_text:
                date_text = f"{date_text} {item.time_text}"
        else:
            date_text = f"{_format_month_day(item.start)}~{_format_month_day(item.end)}"
        display_items.append(
            {"group": group, "label": item.label, "url": item.url, "date_text": date_text}
        )
    return display_items


@login_required
def activity_calendar(request):
    """활동 달력 SSR 뷰.

    event_calendar와 마찬가지로 표시 전용이다: month/date 파싱은
    _parse_calendar_month/_parse_calendar_date 헬퍼를 그대로 재사용하고
    (규칙 동일), 조회/그리드 생성 실패는 같은 방식으로 완화된다
    (calendar_error="query_failed", 절대 500이 아니다).
    archive.activity_calendar_queries.list_user_activity_for_month가 어느 활동이 어느
    날짜에 속하는지를 소유한다 — 이 뷰는 이미 계산된 결과를 날짜별로
    묶고(그리드 점 카운트/종류) 선택된 날짜의 행들을 표시용 dict로 바꿀
    뿐이다.

    컨텍스트 계약(프론트가 이 키들을 기준으로 템플릿을 병행 개발한다):
    calendar_error(None|"invalid"|"query_failed"), month_label, weeks(주당
    7칸 리스트, 각 칸은 {date, in_month, today, selected, count, kinds,
    items, more_count} — count/kinds/items는 서로 일치하며 항상 "status"
    그룹을 제외한다. 상태만 있는 날은 셀뿐 아니라 어디서든 빈 것처럼
    카운트/표시된다(아래 selected_items/kind_counts도 마찬가지). `items`는
    그날의 활동 앞 2개를 {group, label}로, `more_count`는 남은 개수),
    selected_date, selected_items({group, label, url, date_text} 목록
    — archive.activity_calendar_queries.CalendarActivityItem의 label/url/time_text에서
    가져온다, _build_selected_activity_items 참고. 여기도 "status" 그룹
    행은 제외), prev_month/next_month, extra_query(type=만 포함, month/date
    제외), selected_types, has_any_items(현재 type 필터 기준, 표시 중인
    달 전체 — items_by_date에서 유도하므로 위 count/items처럼 "status"
    그룹도 제외한다. 상태만 있는 달은 진짜 빈 달과 똑같이 빈 상태 CTA를
    보여준다), kind_counts(보이는 4개 그룹 -> 카운트 dict, 표시 중인 달
    기준, **현재 ?type= 필터와 무관**하다 — 필터가 조회를 좁히지 않았으면
    `items`를 그대로 재사용하고, 필터가 있으면 필터 없는
    list_user_activity_for_month를 한 번 더 호출한다. 그래야 범례에서
    kind를 다시 켰을 때 필터링된 값의 0이 아니라 실제 카운트가 보인다),
    kind_filters(보이는 4개 그룹을 클릭 가능한 범례 필터로:
    list of {group, count, is_active, toggle_url}. count는 kind_counts와
    같고, toggle_url은 비활성이면 현재 ?type= 선택에 그룹을 더하고
    활성이면 빼는 완전한 /archive/calendar/ URL이며 항상 month/date를
    보존한다), reset_filter_url(?type=을 전부 지우고 month/date는 보존한
    완전한 /archive/calendar/ URL — 여러 개를 토글한 선택을 되돌리는
    "전체 보기" 기능), status_counts(archive.queries.user_status_counts
    (user)를 그대로 — 마스트헤드의 전체 기간 예정/방문 완료/놓침 합계로
    표시 중인 달과 무관하다. 두 집계가 하나로 뒤섞이지 않도록 일부러
    kind_counts와 다른 컨텍스트 키로 둔다), q(현재 ?q= 검색어, 비어
    있어도 항상 존재), search_no_match(빈 값이 아닌 q가 제출됐는데
    아무것도 매치되지 않았을 때만 True — 검색창 값과 이 플래그로
    템플릿이 month/date를 재설정하지 않고 인라인 무매치 안내를 보여줄 수
    있다. 매치됐을 때의 리다이렉트 쪽은 아래 _search_activity_date_jump
    참고).

    active_filter_count(필터 패널의 "N개 선택됨" 표시)는 일부러 이
    컨텍스트에 없다: 이 화면에서는 범례 방식의 kind_filters로 대체하며
    필터 패널을 없앴다 — event_calendar 자체의 active_filter_count
    컨텍스트 키는 그대로 유지된다.

    "status"는 ?type=status 북마크 하위 호환만을 위해 실재하는 매치
    가능 그룹으로 남아 있다(_ACTIVITY_TYPE_GROUPS는 그대로) — 위의 모든
    렌더링/집계 소비처가 _visible_activity_group으로 걸러내므로, 그런
    북마크는 이제 (예전의 걸러지지 않은 카운트 대신) 크래시 없이 진짜로
    빈 날을 안정적으로 보여준다.

    하위 내비게이션 활성 상태 참고: 기존 archive/* 템플릿
    (templates/core/archive/*.html)은
    `{% include "core/partials/_archive_nav.html" with active="..." %}`를
    뷰 컨텍스트 키가 아니라 템플릿에 직접 하드코딩한다 — 따를 만한
    기존 "archive_nav_active" 류 컨텍스트 관례가 없어 여기서도 추가하지
    않았다(_archive_nav.html과 그것을 포함하는 모든 템플릿을 확인함).
    """
    today = timezone.localdate()

    year, month, calendar_error = _parse_calendar_month(request.GET.get("month"), today=today)
    selected_date = None
    if calendar_error is None:
        selected_date, calendar_error = _parse_calendar_date(
            request.GET.get("date"), year=year, month=month, today=today
        )

    if calendar_error:
        year, month = today.year, today.month
        selected_date = today

    selected_types = _parse_activity_type_filter(request)
    kinds = None
    if selected_types:
        kinds = [kind for type_group in selected_types for kind in _ACTIVITY_TYPE_GROUPS[type_group]]

    q = request.GET.get("q", "").strip()
    search_no_match = False
    if calendar_error is None and q:
        redirect_response, search_no_match = _search_activity_date_jump(
            request, q=q, selected_types=selected_types
        )
        if redirect_response is not None:
            return redirect_response

    try:
        items = list(
            list_user_activity_for_month(request.user, year=year, month=month, kinds=kinds)
        )
    except Exception:
        logger.exception(
            "Failed to query activity calendar for year=%s month=%s", year, month
        )
        items = []
        if calendar_error is None:
            calendar_error = "query_failed"

    # kind_counts는 반드시 필터와 무관하게 유지해야 한다: 이미 필터링된
    # `items`에서 유도하면 현재 숨겨진 모든 kind가 0이 되어 범례의 "다시
    # 켜면 몇 개" 안내가 깨진다. ?type= 필터가 조회를 좁히지 않았으면
    # (kinds가 None) `items`를 그대로 재사용하고, 필터가 있을 때만
    # 필터 없이 다시 조회한다.
    if kinds is None:
        all_kind_items = items
    else:
        try:
            all_kind_items = list(
                list_user_activity_for_month(request.user, year=year, month=month, kinds=None)
            )
        except Exception:
            logger.exception(
                "Failed to query unfiltered activity kind counts for year=%s month=%s",
                year,
                month,
            )
            all_kind_items = []

    kind_counts = dict.fromkeys(_VISIBLE_ACTIVITY_TYPE_GROUPS, 0)
    for item in all_kind_items:
        group = _visible_activity_group(item.kind)
        if group is not None:
            kind_counts[group] += 1

    items_by_date = defaultdict(list)
    for item in items:
        if _visible_activity_group(item.kind) is None:
            continue
        if item.date is not None:
            items_by_date[item.date].append(item)
        else:
            day = item.start
            while day <= item.end:
                items_by_date[day].append(item)
                day += timedelta(days=1)

    has_any_items = bool(items_by_date)

    try:
        grid = month_grid(year, month)
    except Exception:
        # event_calendar에도 있는 core.calendar_grid.month_grid의 알려진
        # 한계(year=1/9999 경계 채움 셀)와 동일하다 — 근본 수정은 이번
        # 변경 범위 밖이라 여기서도 완화만 한다.
        logger.exception(
            "Failed to build activity calendar grid for year=%s month=%s", year, month
        )
        grid = []
        if calendar_error is None:
            calendar_error = "query_failed"

    weeks = [
        [
            {
                "date": cell.date,
                "in_month": cell.in_month,
                "today": cell.date == today,
                "selected": cell.date == selected_date,
                "count": len(items_by_date.get(cell.date, [])),
                "kinds": sorted(
                    {_visible_activity_group(day_item.kind) for day_item in items_by_date.get(cell.date, [])}
                ),
                "items": [
                    {"group": _visible_activity_group(day_item.kind), "label": day_item.label}
                    for day_item in items_by_date.get(cell.date, [])[:2]
                ],
                "more_count": max(0, len(items_by_date.get(cell.date, [])) - 2),
            }
            for cell in week
        ]
        for week in grid
    ]

    selected_items = _build_selected_activity_items(items_by_date.get(selected_date, []))

    prev_year, prev_month_num = _adjacent_month(year, month, -1)
    next_year, next_month_num = _adjacent_month(year, month, 1)

    context = {
        "calendar_error": calendar_error,
        "month_label": f"{year}년 {month}월",
        "weeks": weeks,
        "selected_date": selected_date,
        "selected_items": selected_items,
        "prev_month": f"{prev_year:04d}-{prev_month_num:02d}",
        "next_month": f"{next_year:04d}-{next_month_num:02d}",
        "extra_query": _activity_extra_query(selected_types),
        "selected_types": selected_types,
        "has_any_items": has_any_items,
        "kind_counts": kind_counts,
        "kind_filters": _activity_kind_filters(
            year=year,
            month=month,
            selected_date=selected_date,
            selected_types=selected_types,
            kind_counts=kind_counts,
        ),
        "reset_filter_url": _activity_filter_url(
            year=year, month=month, selected_date=selected_date, types=[]
        ),
        "status_counts": user_status_counts(request.user),
        "q": q,
        "search_no_match": search_no_match,
    }
    return render(request, "core/archive/calendar.html", context)


def _search_activity_date_jump(request, *, q, selected_types):
    """활동 달력의 ?q= 날짜 이동 검색을 처리한다: 비어 있지 않은 `q`는
    표시 중인 달뿐 아니라 사용자의 전체 활동 기록을 검색하고, 매치되면
    그 날짜로 PRG 리다이렉트 응답을 반환한다. 매치가 없으면 (None,
    True)를 반환해 호출자가 지금 파싱된 month/date를 그대로 렌더링하게
    한다(검색이 빗나갔다고 오늘로 되돌아가면 안 된다).

    호출자가 selected_types를 명시하지 않았어도 "status"는 이동 대상에서
    항상 제외된다(_visible_activity_group과 동일) — 매치가 숨겨진 상태
    변경뿐인 날짜로 이동하면 선택 날짜 영역이 텅 비어 보인다. 활성
    type= 필터는 그리드를 좁히는 것과 같은 방식으로 검색도 좁혀서,
    이동이 사용자 본인의 필터로 숨긴 kind를 드러내는 일이 없다.
    """
    search_group_names = [
        group
        for group in (selected_types or list(_ACTIVITY_TYPE_GROUPS))
        if group != "status"
    ]
    search_kinds = [
        kind for group in search_group_names for kind in _ACTIVITY_TYPE_GROUPS[group]
    ]

    try:
        match_date = find_latest_activity_date_for_query(request.user, q, kinds=search_kinds)
    except Exception:
        logger.exception("Failed to search activity calendar for q=%r", q)
        match_date = None

    if match_date is None:
        return None, True

    redirect_params = [
        ("month", f"{match_date.year:04d}-{match_date.month:02d}"),
        ("date", match_date.isoformat()),
    ]
    redirect_params += [("type", value) for value in selected_types]
    redirect_url = f"{reverse('archive-calendar-page')}?{urlencode(redirect_params)}#selected-date"
    return redirect(redirect_url), False
