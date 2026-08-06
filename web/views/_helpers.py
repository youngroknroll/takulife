"""여러 뷰 그룹(이벤트/활동/아카이브/컬렉션)이 함께 쓰는 표시·조회 헬퍼."""

from datetime import datetime

from django.shortcuts import render
from django.utils import timezone

from archive.models import UserEventStatus
from archive.queries import user_interest_event_ids
from core.calendar_grid import default_selected_date
from core.vocab import ARCHIVE_STATUS_LABELS, CATEGORY_LABELS, EVENT_STATUS_LABELS, REGION_LABELS
from events.presenters import derive_event_display, is_recently_added


def _archive_query(request) -> str:
    """요청에서 ?q= 검색어를 꺼내 정리한다.

    앞뒤 공백을 지우고 100자로 자른다 — 임의로 긴 q 값이 조회 시간을
    늘리거나 오류를 일으키지 않게 한다.
    """
    return (request.GET.get("q") or "").strip()[:100]


def _attach_display(events, *, today=None, user=None):
    """각 행사에 파생 표시값(status_slug, status_label, dday)을 붙인다.

    ``user``가 인증된 사용자면 ``user_status``(그 행사에 대한 사용자
    본인의 archive 상태 slug, 없으면 "")도 붙여서 발견 카드가 고정된
    기본값이 아니라 실제 상태를 반영하게 한다.

    템플릿이 점 표기법을 깔끔히 쓸 수 있도록 순수 dict 리스트를 반환한다.
    """
    events = list(events)
    event_ids = [event.id for event in events]

    user_status_map = {}
    user_interest_map = {}
    if user is not None and user.is_authenticated and events:
        status_today = today if today is not None else timezone.localdate()
        user_status_map = {
            event_id: (status_val, status_id)
            for event_id, status_val, status_id in (
                UserEventStatus.objects.filter(user=user, event_id__in=event_ids)
                .with_derived_status(today=status_today)
                .values_list("event_id", "derived_status", "id")
            )
        }
        user_interest_map = user_interest_event_ids(user, event_ids=event_ids)

    result = []
    for event in events:
        display = derive_event_display(event, today=today)
        status_slug = display["status"]
        user_status, user_status_id = user_status_map.get(event.id, ("", None))
        interest_id = user_interest_map.get(event.id)
        result.append(
            {
                "event": event,
                "status_slug": status_slug,
                "status_label": EVENT_STATUS_LABELS.get(status_slug, ""),
                "category_label": CATEGORY_LABELS.get(event.category, event.category),
                "category_slug": event.category,
                "region_label": REGION_LABELS.get(event.region, "") if event.region else "",
                "dday": display["dday"],
                "is_new": is_recently_added(event, today=today),
                "user_status": user_status,
                "user_status_id": user_status_id,
                "user_status_label": ARCHIVE_STATUS_LABELS.get(user_status, ""),
                "user_interested": interest_id is not None,
                "user_interest_id": interest_id,
            }
        )
    return result


def _adjacent_month(year, month, delta):
    """(year, month)에서 `delta`개월 떨어진 (year, month)를 반환한다. 연도
    경계를 넘어가면 자동으로 넘어간다(delta는 보통 -1 또는 +1)."""
    total = year * 12 + (month - 1) + delta
    new_year, new_month0 = divmod(total, 12)
    return new_year, new_month0 + 1


def _parse_calendar_month(raw_month, *, today):
    """?month=YYYY-MM 파라미터를 파싱한다. (year, month, error)를 반환하며
    error는 성공 시 None, 형식이 잘못됐거나 범위를 벗어나면 "invalid".

    키가 아예 *없는* 경우(raw_month가 None)에만 오늘 달을 기본값으로
    쓴다 — 키는 있지만 값이 빈 경우(?month=)는 그 자체로 형식 오류이지
    "없음"이 아니다. 이 둘을 구분하려면 호출자가 기본값 없이
    request.GET.get("month")를 넘겨야 한다. 여기서 두 경우를 다 ""로
    합치면 `?month=`을 month 키가 아예 없는 것과 조용히 똑같이 취급하게
    된다.
    """
    if raw_month is None:
        return today.year, today.month, None
    try:
        parsed = datetime.strptime(raw_month, "%Y-%m")
    except ValueError:
        return None, None, "invalid"
    return parsed.year, parsed.month, None


def _parse_calendar_date(raw_date, *, year, month, today):
    """이미 정해진 (year, month)를 기준으로 ?date=YYYY-MM-DD 파라미터를
    파싱한다. (date, error)를 반환하며 error는 성공 시 None, 형식이
    잘못됐거나 존재하지 않는 날짜이거나 표시 중인 달을 벗어나면 "invalid".

    키가 아예 *없는* 경우(raw_date가 None)에만 기본 선택 규칙으로
    대체한다 — 값이 빈 경우(?date=)는 형식 오류다. _parse_calendar_month와
    같은 "없음 vs 빈 값" 구분을 유지하며, 호출자는 기본값 없이
    request.GET.get("date")를 넘겨야 한다.
    """
    if raw_date is None:
        return default_selected_date(year=year, month=month, today=today), None
    try:
        parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return None, "invalid"
    if (parsed.year, parsed.month) != (year, month):
        return None, "invalid"
    return parsed, None


def _render_archive_list(request, *, full_template, fragment_template, context):
    """archive 목록 페이지 전체를 렌더링하거나, 라이브 검색용 결과
    프래그먼트만 렌더링한다.

    요청에 ``?partial=1``이 있으면 라이브 검색 JS가 교체 가능한 결과
    영역(목록 + 빈 상태 + 페이저)만 필요로 하므로 전체 페이지 대신
    프래그먼트 템플릿만 렌더링한다. 이건 내부 분기일 뿐 별도의 비인증
    엔드포인트가 아니라 호출한 뷰의 인증/CSRF 데코레이터가 그대로
    적용된다. 그 외 값(또는 없음)은 전체 페이지를 렌더링해 JS 없이도
    GET 폼이 그대로 동작한다.
    """
    template = fragment_template if request.GET.get("partial") == "1" else full_template
    return render(request, template, context)


def _subject_view(obj):
    """archive 행의 대상(공식 Event 또는 비공식 PersonalEntry)을 일관되고
    null 안전하게 보여준다.

    이 대상 패턴을 따르는 archive 행(VisitRecord, EventInterest,
    UserEventStatus)은 전부 ``event``/``event_id``와 ``personal_entry``를
    노출하는데, 이 함수가 둘을 하나의 dict로 합쳐 템플릿과 JS가 어느 FK가
    설정됐는지로 분기하지 않게 한다. ``subject_type``/``subject_id``는
    API 응답을 이루고, 비공개 항목(공개 페이지 없음)은 ``detail_url``이
    비어 있으며, 굿즈는 기간 날짜가 None이다.
    """
    if obj.event_id is not None:
        event = obj.event
        return {
            "title": event.title,
            "category_label": CATEGORY_LABELS.get(event.category, event.category),
            "category_slug": event.category,
            "location": event.location_name,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "is_official": True,
            "kind": "",
            "subject_type": "event",
            "subject_id": event.id,
            "detail_url": f"/events/{event.id}/",
        }
    entry = obj.personal_entry
    return {
        "title": entry.title,
        "category_label": entry.category,
        "location": entry.location_name,
        "start_date": None,
        "end_date": None,
        "is_official": False,
        "kind": entry.kind,
        "subject_type": "personal",
        "subject_id": entry.id,
        "detail_url": "",
    }
