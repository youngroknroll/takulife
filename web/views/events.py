"""홈, 행사 목록/캘린더/상세 — 공개 행사 열람 뷰 그룹."""

from collections import defaultdict
from datetime import date, timedelta
import json
import logging
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import truncatechars
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import get_language, gettext
from rest_framework.exceptions import ValidationError

from archive.models import UserEventStatus
from archive.queries import (
    list_user_collection_items,
    list_user_unrecorded_visited_statuses,
    list_user_upcoming_planned_events,
    user_collection_item_summary_counts,
    user_interest_count,
    user_interest_event_ids,
    user_visit_record_counts,
)
from core.calendar_grid import month_grid
from core.presenters import build_website_json_ld
from core.vocab import (
    ARCHIVE_STATUS_LABELS,
    CATEGORY,
    CATEGORY_LABELS,
    EVENT_SORT,
    EVENT_SORT_LABELS,
    EVENT_STATUS,
    EVENT_STATUS_LABELS,
    REGION,
    REGION_LABELS,
)
from events.models import Event
from events.presenters import build_event_json_ld, derive_event_display
from events.queries import (
    PUBLIC_LISTING_PAGE_SIZE,
    list_published_events,
    list_published_events_for_month,
    parse_public_listing_params,
)
from web.public_cache import home_public_sections, public_category_choices, public_month_events
from web.views._helpers import (
    _attach_display,
    _attach_display_many,
    _bounded_month_param,
    _is_public_calendar_month,
    _parse_public_calendar_date,
    _parse_public_calendar_month,
    _redirect_without_calendar_params,
    _subject_view,
)

logger = logging.getLogger(__name__)

# 홈 달력 칸의 점 최대 개수(디자인 핸드오프 기준).
HOME_CALENDAR_DOT_LIMIT = 4
# 아젠다 행은 달력 아래 여백을 줄이려 3건으로 둔다.
HOME_CALENDAR_AGENDA_LIMIT = 3


def _dedupe_category_slugs(slugs, *, limit):
    """등장 순서대로 중복·빈 값을 빼고 최대 limit개만 남긴다."""
    seen = []
    for slug in slugs:
        if not slug or slug in seen:
            continue
        seen.append(slug)
        if len(seen) == limit:
            break
    return seen


def _events_by_date(events):
    """행사별 시작일~종료일(없으면 시작일 하루)을 날짜별 목록으로 펼친다."""
    events_by_date = defaultdict(list)
    for event in events:
        day = event.start_date
        end = event.end_date or event.start_date
        while day <= end:
            events_by_date[day].append(event)
            day += timedelta(days=1)
    return events_by_date


def _home_calendar_cell(cell, events_by_date, *, today, selected_date):
    """달력 칸 하나에 오늘·선택·건수·카테고리 표시값을 붙인다.

    채움 칸은 표시 달과 겹치는 행사만 알고 있어 표시하지 않는다.
    """
    cell_events = events_by_date.get(cell.date, []) if cell.in_month else []
    return {
        "date": cell.date,
        "in_month": cell.in_month,
        "today": cell.date == today,
        "selected": cell.date == selected_date,
        "count": len(cell_events),
        "categories": _dedupe_category_slugs(
            [event.category for event in cell_events], limit=HOME_CALENDAR_DOT_LIMIT
        ),
        "linkable": cell.date is not None and _is_public_calendar_month(cell.date, today=today),
    }


def _home_calendar_weeks(grid, events_by_date, *, today, selected_date):
    """달력 그리드 칸에 오늘·선택·건수·카테고리 표시값을 붙인다."""
    return [
        [
            _home_calendar_cell(cell, events_by_date, today=today, selected_date=selected_date)
            for cell in week
        ]
        for week in grid
    ]


def _home_calendar_context(year, month, calendar_error, raw_date, *, today):
    """홈 이벤트 달력 섹션 컨텍스트를 만든다. year/month/calendar_error는
    호출자(home)가 이미 파싱한 달 — 범위 밖 판단을 조회 전에 끝내기
    위해서다.
    """
    selected_date = None
    if calendar_error is None:
        selected_date, calendar_error = _parse_public_calendar_date(
            raw_date, year=year, month=month, today=today
        )

    # 홈은 달력 전용 화면이 아니라 잘못된 값은 알리지 않고 이번 달로 돌아간다.
    if calendar_error:
        year, month = today.year, today.month
        selected_date = today

    events = public_month_events(year=year, month=month, today=today)
    events_by_date = _events_by_date(events)

    grid = month_grid(year, month)
    weeks = _home_calendar_weeks(grid, events_by_date, today=today, selected_date=selected_date)
    selected_events = events_by_date.get(selected_date, [])
    month_categories = {event.category for event in events if event.category}
    legend = [
        {"slug": slug, "label": label} for slug, label in CATEGORY if slug in month_categories
    ]
    return {
        "year": year,
        "month": month,
        "month_start": date(year, month, 1),
        "month_param": f"{year:04d}-{month:02d}",
        "prev_month": _bounded_month_param(year, month, -1, today=today),
        "next_month": _bounded_month_param(year, month, 1, today=today),
        "selected_date": selected_date,
        "selected_is_today": selected_date == today,
        "selected_count": len(selected_events),
        # 찜·방문 등 사용자별 상태는 쓰지 않아 user를 넘기지 않는다(조회 2건 회피).
        "selected_rows": _attach_display(selected_events[:HOME_CALENDAR_AGENDA_LIMIT], today=today),
        "legend": legend,
        "weeks": weeks,
    }


def home(request):
    today = timezone.localdate()
    year, month, calendar_error = _parse_public_calendar_month(
        request.GET.get("month"), today=today
    )
    # 범위 밖 달은 조회 전에 돌려보낸다.
    if calendar_error == "out_of_range":
        return _redirect_without_calendar_params(request)
    public_sections = home_public_sections(today=today)

    # 홈 카테고리 쌍과 건수는 공개 캐시에서 받고, 라벨 번역은 요청마다 한다.
    category_tiles = []
    for slug, label in public_sections["featured_category_pairs"]:
        text, lang = _translate_category_label(label)
        category_tiles.append(
            {
                "slug": slug,
                "label": text,
                "lang": lang,
                "count": public_sections["category_counts"].get(slug, 0),
            }
        )

    # 구간마다 _attach_display를 따로 부르면 사용자 상태·관심 조회가
    # 구간 수만큼 늘어나므로, 모든 구간 행사를 모아 한 번에 처리한다.
    # 건수·카테고리 쌍은 행사 목록이 아니라 넣지 않는다.
    sections = {
        key: public_sections[key]
        for key in ("ongoing_rows", "closing_rows", "recent_rows", "featured_event_rows")
    }
    if request.user.is_authenticated:
        sections = {
            **sections,
            "upcoming_planned": list_user_upcoming_planned_events(request.user, today=today)[:4],
        }
    rows_by_section = _attach_display_many(sections, today=today, user=request.user)

    context = {
        "ongoing_rows": rows_by_section["ongoing_rows"],
        "closing_rows": rows_by_section["closing_rows"],
        "recent_rows": rows_by_section["recent_rows"],
        "category_tiles": category_tiles,
        "featured_event_rows": rows_by_section["featured_event_rows"],
        "home_calendar": _home_calendar_context(
            year, month, calendar_error, request.GET.get("date"), today=today
        ),
        "json_ld_script": _json_ld_script(build_website_json_ld(request.build_absolute_uri("/"))),
    }

    if request.user.is_authenticated:
        user = request.user
        collection_summary = user_collection_item_summary_counts(user)
        recent_goods = list(list_user_collection_items(user)[:5])
        # _build_archive_status_rows를 거치지 않고 직접 만든다: 그 헬퍼는
        # .derived_status(annotation 전용 속성)를 무조건 읽는데, 이 행의
        # 상태는 구조상 항상 "visited"이므로(list_user_unrecorded_visited_
        # statuses가 이미 그것만 걸러낸다) 별도 유도가 필요 없고
        # _subject_view 자체도 derived_status에 의존하지 않으므로 이
        # 원본 슬라이스를 그대로 써도 안전하다.
        unrecorded_rows = [
            {"status_id": row.pk, "subject": _subject_view(row)}
            for row in list_user_unrecorded_visited_statuses(user)[:5]
        ]
        upcoming_rows = rows_by_section["upcoming_planned"]
        context.update(
            {
                "collection_summary": collection_summary,
                # 통계 칸이 2개에서 4개로 늘었다. 보유/구함은
                # collection_summary가 담당하고, 나머지 두 칸은 방문 기록 수와
                # 찜 수 — 둘 다 단순 count 쿼리다.
                "snapshot_visit_count": user_visit_record_counts(user)["total_count"],
                "snapshot_interest_count": user_interest_count(user),
                "recent_goods": recent_goods,
                "unrecorded": unrecorded_rows,
                "upcoming_planned": upcoming_rows,
                "snapshot_active": bool(unrecorded_rows)
                or bool(recent_goods)
                or bool(upcoming_rows)
                or (collection_summary["owned_count"] + collection_summary["wanted_count"] > 0),
            }
        )

    return render(request, "core/home.html", context)


def _active_filter_chips(*, q, selected_region, selected_category, selected_status):
    """활성 q/region/category/status 필터를 사람이 읽을 수 있는 칩으로
    요약한다(Eventbrite 스타일). event_list와 event_calendar가 공유해
    두 페이지가 같은 선택으로부터 같은 칩 라벨을 만들게 한다 — 새 조회
    없이 호출자가 이미 파싱한 값에 라벨만 붙인다."""
    chips = []
    if q:
        chips.append(gettext("검색: %(q)s") % {"q": q})
    for region in selected_region:
        chips.append(REGION_LABELS.get(region, region))
    for category in selected_category:
        chips.append(CATEGORY_LABELS.get(category, category))
    if selected_status:
        chips.append(EVENT_STATUS_LABELS.get(selected_status, selected_status))
    return chips


def _has_hangul(text):
    # 가드가 한국어 문자열 상수를 막으므로 코드포인트 범위로 판별한다.
    return any(0xAC00 <= ord(ch) <= 0xD7A3 for ch in text)


def _translate_category_label(label):
    """카테고리 라벨을 요청 언어로 옮기고 (텍스트, lang)을 돌려준다.

    어휘 msgid와 글자가 같은 라벨만 번역되고 스태프가 새로 만든 라벨은 한국어
    그대로 남는다(우연히 다른 msgid와 같은 라벨은 그 번역이 붙는다).
    번역되지 않은 한글 라벨이 비한국어 화면에 섞일 때만 lang="ko"를 돌려준다.
    """
    text = gettext(label)
    language = get_language()
    is_korean_ui = language is None or language.startswith("ko")
    if not is_korean_ui and text == label and _has_hangul(label):
        return text, "ko"
    return text, ""


def _translated_category_choices():
    """소비자 필터용 (slug, 번역 라벨, lang) 목록. 원문은 공개 캐시에서
    받고 번역은 요청마다 한다."""
    return [(slug, *_translate_category_label(label)) for slug, label in public_category_choices()]


def event_list(request):
    page_obj = None
    total_count = 0
    event_rows = []

    # 잘못됐거나 인식되지 않는 필터 값은 "매치 없음"으로 취급해, 열람
    # 페이지가 오류 화면 대신 빈 상태("이벤트 없음")로 완화된다. JSON
    # API는 같은 입력을 여전히 400으로 거부한다.
    try:
        params = parse_public_listing_params(request.GET)
        # 호출자가 status 필터를 보내지 않으면 "active"(진행 중/예정)로
        # 기본값을 둔다. 파싱 전이 아니라 반드시 파싱 후에 둬야 한다:
        # "active"는 일부러 STATUS_CHOICES에 없어서, 원본
        # request.GET에 끼워 넣으면 parse_public_listing_params가
        # ValidationError를 던지고 아래 except가 그걸 조용히 빈 상태
        # 페이지로 삼켜버린다.
        if not params.get("status"):
            params = {**params, "status": "active"}
        qs = list_published_events(params)
        paginator = Paginator(qs, PUBLIC_LISTING_PAGE_SIZE)
        page_obj = paginator.get_page(request.GET.get("page"))
        # 페이지 나누기가 이미 센 전체 건수를 다시 쓴다 — 따로 세면 같은 COUNT가 두 번 나간다.
        total_count = paginator.count
        event_rows = _attach_display(page_obj.object_list, user=request.user)
    except ValidationError:
        pass

    selected_region = request.GET.getlist("region")
    selected_category = request.GET.getlist("category")
    selected_status = request.GET.get("status", "")
    q = request.GET.get("q", "")
    selected_sort = request.GET.get("sort", "")

    # 예전 QueryDict가 아니던 코드 경로에서 남은 방어적 스칼라 감싸기다.
    # 지금은 도달 불가능하다: 같은 키에서 getlist(k)가 비어 있는 것과
    # get(k)가 None인 것은 항상 같이 성립하므로 `not getlist and get`은
    # 절대 참이 될 수 없다. 삭제하지 않고 남겨뒀으며 커버리지에서는
    # 제외한다 — 별도 정리 작업에서 지워도 안전하다.
    if not selected_region and request.GET.get("region"):  # pragma: no cover
        selected_region = [request.GET.get("region")]
    if not selected_category and request.GET.get("category"):  # pragma: no cover
        selected_category = [request.GET.get("category")]

    active_filters = bool(q or selected_region or selected_category or selected_status)

    # 활성 필터를 사람이 읽을 수 있는 칩으로 요약한다(Eventbrite 스타일).
    active_filter_chips = _active_filter_chips(
        q=q,
        selected_region=selected_region,
        selected_category=selected_category,
        selected_status=selected_status,
    )

    context = {
        "page_obj": page_obj,
        "total_count": total_count,
        "event_rows": event_rows,
        "active_filters": active_filters,
        "active_filter_chips": active_filter_chips,
        "category_labels": CATEGORY_LABELS,
        # 필터 UI용 어휘 튜플
        "CATEGORY": _translated_category_choices(),
        "REGION": REGION,
        "EVENT_STATUS": EVENT_STATUS,
        # 정렬이 사이드바 필터 폼에서 결과 상단 토글 메뉴로 옮겨져,
        # 템플릿이 하드코딩된 <option> 4개 대신 어휘 튜플로 옵션마다
        # 링크 하나씩을 렌더링해야 한다.
        "EVENT_SORT": EVENT_SORT,
        # 현재 선택 값
        "q": q,
        "selected_region": selected_region,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "selected_sort": selected_sort,
        "selected_sort_label": EVENT_SORT_LABELS.get(selected_sort, EVENT_SORT_LABELS[""]),
        # 목록<->달력 전환 링크가 쿼리스트링을 보존하게 한다 —
        # event_list엔 원래 이런 컨텍스트가 없었고, 이미 잘 동작하는
        # 필터 추출을 중복 구현하지 않고 여기서 추가했다.
        "extra_query": _calendar_extra_query(request),
        # 목록 페이지 페이저는 정렬도 보존해야 해서 _calendar_extra_query
        # (달력 전환 계약을 위해 일부러 정렬을 뺀다)를 재사용할 수 없다.
        "pager_query": _event_list_pager_query(request),
    }
    return render(request, "core/events/list.html", context)


def _event_list_pager_query(request):
    """현재 q/region/category/status/sort 필터를 '&key=value'
    쿼리스트링 꼬리로 반환한다(선행 '&',
    templates/core/partials/_pager.html의 extra_query 관례와 동일) —
    템플릿에서 '?page=...' 값 바로 뒤에 같은 컨텍스트 키를 그대로 붙일
    수 있게 한다. _calendar_extra_query와 달리 'sort'를 포함한다: 행사
    목록 페이저는 페이지를 넘나들며 정렬을 보존해야 하지만 달력 전환
    링크는 일부러 그러지 않는다.
    """
    pairs = []
    for key in ("q", "region", "category", "status", "sort"):
        for value in request.GET.getlist(key):
            if value:
                pairs.append((key, value))
    if not pairs:
        return ""
    return "&" + urlencode(pairs)


def _calendar_extra_query(request):
    """현재 q/region/category/status 필터를 '&key=value' 쿼리스트링
    꼬리로 반환한다(선행 '&', templates/core/partials/_pager.html의
    extra_query 관례와 동일) — 템플릿에서 '?month=...'/'?page=...' 값
    바로 뒤에 같은 컨텍스트 키를 그대로 붙일 수 있게 한다. 'sort'와
    달력 전용 'month'/'date' 파라미터는 일부러 제외한다(기존 목록과는
    q/region/category/status만 맞추면 된다).
    """
    pairs = []
    for key in ("q", "region", "category", "status"):
        for value in request.GET.getlist(key):
            if value:
                pairs.append((key, value))
    if not pairs:
        return ""
    return "&" + urlencode(pairs)


def event_calendar(request):
    """행사 달력 SSR 뷰.

    표시 전용이다: 날짜 범위/겹침 비즈니스 규칙은 계속
    events.queries.list_published_events_for_month과
    core.calendar_grid.month_grid가 소유한다 — 이 뷰는 요청 파라미터를
    파싱해 그것들을 호출하고 결과를 아래 템플릿 컨텍스트 계약대로
    재구성할 뿐이다(키는 고정, 이름 바꾸지 말 것 — 프론트가 이 계약을
    기준으로 템플릿을 병행 개발 중이다):

    calendar_error(None|"invalid"|"query_failed"), month_label
    (요청 언어의 연월 표기, 예 "2026년 3월"), weeks(주당 7칸 리스트, 각 칸은 {date, in_month,
    today, selected, items[{title,url}](최대 2개), more_count, count}),
    selected_date, selected_events, prev_month/next_month("YYYY-MM"),
    extra_query, 그리고 event_list가 이미 제공하는 것과 같은 필터
    패널 컨텍스트 키(CATEGORY는 (slug, label, lang) 3-튜플, REGION/EVENT_STATUS,
    q/selected_region/selected_category/selected_status/selected_sort/
    selected_sort_label)를 그대로 담아 기존 필터 체크 마크업을 그대로
    재사용할 수 있게 한다.
    """
    today = timezone.localdate()

    year, month, calendar_error = _parse_public_calendar_month(
        request.GET.get("month"), today=today
    )
    # 범위 밖 달은 조회 전에 돌려보낸다.
    if calendar_error == "out_of_range":
        return _redirect_without_calendar_params(request)
    selected_date = None
    if calendar_error is None:
        selected_date, calendar_error = _parse_public_calendar_date(
            request.GET.get("date"), year=year, month=month, today=today
        )

    if calendar_error:
        year, month = today.year, today.month
        selected_date = today

    try:
        params = parse_public_listing_params(request.GET)
    except ValidationError:
        # event_list와 같은 완화 방식: 인식되지 않거나 잘못된 필터 값은
        # calendar_error와 무관하게 "맞는 행사 없음"(빈 달력)이지 절대
        # 오류 화면이 아니다 — "필터 없음"과 구분해 조회 자체를 건너뛴다.
        params = None

    try:
        if params is None:
            events = []
        # 필터 없는 달력만 공개 캐시를 쓴다(필터 조합은 끝이 없어 담지 않는다).
        elif not params:
            events = public_month_events(year=year, month=month, today=today)
        else:
            events = list(list_published_events_for_month(params, year=year, month=month))
    except Exception:
        logger.exception("Failed to query events calendar for year=%s month=%s", year, month)
        events = []
        if calendar_error is None:
            calendar_error = "query_failed"

    events_by_date = _events_by_date(events)

    try:
        grid = month_grid(year, month)
    except Exception:
        # core.calendar_grid.month_grid는 앞뒤 채움 주가 1~9999년 범위
        # 밖의 날짜를 필요로 하는 달에서 예외를 던질 수 있다(예:
        # year=1/month=1은 "0년 12월" 채움 날짜 며칠이 필요하다) — 이미
        # 병합된 그리드 모듈의 알려진 한계다(자체 단위 테스트는 2026년만
        # 다뤘다). 근본 수정은 이번 변경 권한 범위 밖이라 여기서는
        # 완화만 하고 core/calendar_grid.py 후속 수정으로 남겨둔다.
        logger.exception("Failed to build calendar grid for year=%s month=%s", year, month)
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
                "items": [
                    {
                        "title": event.title,
                        "url": reverse("event-detail-page", args=[event.id]),
                        "category_slug": event.category,
                    }
                    for event in events_by_date.get(cell.date, [])[:2]
                ],
                "more_count": max(len(events_by_date.get(cell.date, [])) - 2, 0),
                "count": len(events_by_date.get(cell.date, [])),
                "linkable": cell.date is not None
                and _is_public_calendar_month(cell.date, today=today),
            }
            for cell in week
        ]
        for week in grid
    ]

    selected_events = _attach_display(
        events_by_date.get(selected_date, []), today=today, user=request.user
    )

    selected_region = request.GET.getlist("region")
    selected_category = request.GET.getlist("category")
    selected_status = request.GET.get("status", "")
    q = request.GET.get("q", "")
    selected_sort = request.GET.get("sort", "")

    context = {
        "calendar_error": calendar_error,
        "month_label": date_format(date(year, month, 1), "YEAR_MONTH_FORMAT"),
        "category_labels": CATEGORY_LABELS,
        "weeks": weeks,
        "selected_date": selected_date,
        "selected_events": selected_events,
        "prev_month": _bounded_month_param(year, month, -1, today=today),
        "next_month": _bounded_month_param(year, month, 1, today=today),
        "extra_query": _calendar_extra_query(request),
        "active_filter_chips": _active_filter_chips(
            q=q,
            selected_region=selected_region,
            selected_category=selected_category,
            selected_status=selected_status,
        ),
        # 필터 패널 컨텍스트. event_list와 그대로 맞춰 기존 필터 체크
        # 마크업을 그대로 재사용할 수 있게 한다.
        "CATEGORY": _translated_category_choices(),
        "REGION": REGION,
        "EVENT_STATUS": EVENT_STATUS,
        "q": q,
        "selected_region": selected_region,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "selected_sort": selected_sort,
        "selected_sort_label": EVENT_SORT_LABELS.get(selected_sort, EVENT_SORT_LABELS[""]),
        "active_filter_count": len(selected_region)
        + len(selected_category)
        + (1 if selected_status else 0)
        + (1 if q else 0),
    }
    return render(request, "core/events/calendar.html", context)


# </script>가 포함된 제목이 스크립트 블록을 조기 종료시키지 못하게 이스케이프한다.
_JSON_LD_ESCAPES = str.maketrans({"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"})


def _json_ld_script(payload):
    if payload is None:
        return None
    # payload에 지연 번역 라벨(Promise)이 섞일 수 있어 활성 언어로 평가하는 Django 인코더를 쓴다.
    return json.dumps(payload, ensure_ascii=False, cls=DjangoJSONEncoder).translate(
        _JSON_LD_ESCAPES
    )


def _build_event_meta_title(event):
    segment = f"{event.work_title} · {event.title}" if event.work_title else event.title
    return f"{truncatechars(segment, 20)} — takulife"


def _build_event_meta_description(event, category_label):
    summary = event.summary.strip()
    if summary:
        return truncatechars(summary, 100)

    if event.end_date and event.start_date and event.end_date != event.start_date:
        period = f"{event.start_date} ~ {event.end_date}"
    elif event.start_date:
        period = str(event.start_date)
    else:
        period = ""

    parts = [str(part) for part in (category_label, event.location_name, period) if part]
    if parts:
        return truncatechars(" · ".join(parts), 100)

    return gettext(
        "타쿠라이프(takulife)에서 팝업스토어 · 콜라보 카페 · 극장 특전 · 굿즈 예약 · 전시를 "
        "검색하고, 방문 상태와 기록을 보관하세요."
    )


def event_detail(request, event_id):
    event = get_object_or_404(Event.objects.published(), pk=event_id)
    # 본문을 받지 않는 HEAD 요청(링크 미리보기·크롤러)은 조회수에 넣지 않는다.
    if request.method != "HEAD":
        Event.objects.increment_view_count(event.pk)
    display = derive_event_display(event)
    status_slug = display["status"]

    user_status = ""
    user_status_id = None
    user_interested = False
    user_interest_id = None
    if request.user.is_authenticated:
        row = (
            UserEventStatus.objects.filter(user=request.user, event=event)
            .with_derived_status(today=timezone.localdate())
            .values_list("derived_status", "id")
            .first()
        )
        if row:
            user_status, user_status_id = row
        interest_map = user_interest_event_ids(request.user, event_ids=[event.id])
        user_interest_id = interest_map.get(event.id)
        user_interested = user_interest_id is not None

    today = timezone.localdate()
    related_events = _attach_display(
        Event.objects.published().related_to(event, today=today, limit=3),
        today=today,
    )

    region_label = REGION_LABELS.get(event.region, "") if event.region else ""
    category_label = CATEGORY_LABELS.get(event.category, event.category)
    meta_description = _build_event_meta_description(event, category_label)
    json_ld_payload = build_event_json_ld(
        event, region_label=region_label, description=meta_description
    )
    if json_ld_payload is not None:
        json_ld_payload = {
            **json_ld_payload,
            "url": request.build_absolute_uri(json_ld_payload["url"]),
        }

    context = {
        "event": event,
        "status_slug": status_slug,
        "status_label": EVENT_STATUS_LABELS.get(status_slug, ""),
        "category_label": category_label,
        "region_label": region_label,
        "dday": display["dday"],
        "user_status": user_status,
        "user_status_id": user_status_id,
        "user_status_label": ARCHIVE_STATUS_LABELS.get(user_status, ""),
        "user_interested": user_interested,
        "user_interest_id": user_interest_id,
        "related_events": related_events,
        "json_ld_script": _json_ld_script(json_ld_payload),
        "meta_title": _build_event_meta_title(event),
        "meta_description": meta_description,
    }
    return render(request, "core/events/detail.html", context)
