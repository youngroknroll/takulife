"""스태프 콘솔 뷰: 게시/초안 이벤트 CRUD와 품질 문제 드릴다운."""
import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.vocab import CATEGORY, CATEGORY_LABELS, REGION, REGION_LABELS
from events.models import Event
from events.queries import (
    QUALITY_WARNING_KEYS,
    STAFF_EVENT_LISTING_PAGE_SIZE,
    list_staff_events,
)
from events.services import (
    DuplicateOfficialUrlError,
    InvalidEventPeriodError,
    MissingOfficialUrlError,
    PublishEventCategoryError,
    PublishEventError,
    PublishEventRegionError,
    PublishEventTitleError,
    create_published_event,
    mark_event_verified,
    republish_event,
    unpublish_event,
    update_published_event,
)

from ..models import StaffActionLog
from ..search import search_term
from ..permissions import staff_console_required
from ..services import (
    EventHasArchiveReferencesError,
    delete_event,
    event_archive_reference_counts,
)
from ._helpers import _action_log_kwargs, _staff_action_metadata

# staff/dashboard.html의 경고 표에 쓰는 문구와 같은 내용이다. 자동 동기화가
# 아니라 손으로 맞춰야 하니, 라벨을 바꾸면 그쪽도 같이 고쳐야 한다.
QUALITY_WARNING_LABELS = {
    "missing_official_url": "공식 URL 없음",
    "ended_still_published": "종료됐지만 게시 중",
    "missing_dates": "날짜 정보 누락",
    "missing_region": "지역 정보 없음",
    "needs_reverification": "시작 임박, 미확인",
}


def _event_quality_badges(event, *, today):
    """이 이벤트가 걸린 품질 경고 라벨 목록을 반환한다.

    게시된 이벤트에만 호출한다 — 이 판정 기준이 게시 상태 이벤트를
    전제하므로, 초안 이벤트에 적용하면 잘못된 배지가 나온다.
    """
    badges = []
    if not event.official_url:
        badges.append(QUALITY_WARNING_LABELS["missing_official_url"])
    if event.end_date and event.end_date < today:
        badges.append(QUALITY_WARNING_LABELS["ended_still_published"])
    if event.start_date is None or event.end_date is None:
        badges.append(QUALITY_WARNING_LABELS["missing_dates"])
    if event.region == "":
        badges.append(QUALITY_WARNING_LABELS["missing_region"])
    return badges


def _build_event_rows(events):
    """템플릿용으로 각 이벤트에 표시 라벨과 품질 배지를 붙인다."""
    today = timezone.localdate()
    rows = []
    for event in events:
        is_published = event.publish_status == Event.PublishStatus.PUBLISHED
        rows.append(
            {
                "event": event,
                "category_label": CATEGORY_LABELS.get(event.category, event.category),
                "region_label": REGION_LABELS.get(event.region, event.region),
                "quality_badges": _event_quality_badges(event, today=today)
                if is_published
                else [],
            }
        )
    return rows


def _selected_event_filters(get_params):
    """?warning=/?publish_status= 값을 허용 목록과 대조해 검증한다.

    목록 화면과 수정 화면(목록으로 돌아가기 링크)이 함께 쓰므로, 모르는
    값은 항상 "필터 없음"으로 통일해 처리한다.
    """
    selected_warning = get_params.get("warning", "")
    if selected_warning not in QUALITY_WARNING_KEYS:
        selected_warning = ""

    selected_publish_status = get_params.get("publish_status", "")
    if selected_publish_status not in Event.PublishStatus.values:
        selected_publish_status = ""

    return selected_warning, selected_publish_status


def _event_filter_query_pairs(get_params):
    selected_warning, selected_publish_status = _selected_event_filters(get_params)
    pairs = []
    if selected_warning:
        pairs.append(("warning", selected_warning))
    if selected_publish_status:
        pairs.append(("publish_status", selected_publish_status))
    return pairs


@staff_console_required
def staff_events(request):
    """게시+초안 이벤트 목록과 품질 경고 드릴다운."""
    selected_warning, selected_publish_status = _selected_event_filters(request.GET)

    search = search_term(request)
    events = list_staff_events(
        warning=selected_warning or None,
        publish_status=selected_publish_status or None,
        search=search,
    )
    paginator = Paginator(events, STAFF_EVENT_LISTING_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    event_rows = _build_event_rows(page_obj.object_list)

    query_pairs = list(_event_filter_query_pairs(request.GET))
    if search:
        query_pairs.append(("q", search))
    pager_query = "&" + urlencode(query_pairs) if query_pairs else ""

    warning_chips = [
        {"key": key, "label": QUALITY_WARNING_LABELS[key]} for key in QUALITY_WARNING_KEYS
    ]

    return render(
        request,
        "staff/events/list.html",
        {
            "event_rows": event_rows,
            "page_obj": page_obj,
            "selected_warning": selected_warning,
            "selected_publish_status": selected_publish_status,
            "pager_query": pager_query,
            "warning_chips": warning_chips,
            "search": search,
        },
    )


EVENT_EDIT_TEXT_FIELDS = (
    "title",
    "category",
    "work_title",
    "location_name",
    "region",
    "official_url",
    "source_name",
    "summary",
)

EVENT_CREATE_BLANK_FORM_VALUES = {
    **{field: "" for field in EVENT_EDIT_TEXT_FIELDS},
    "start_date": "",
    "end_date": "",
}


def _parse_optional_date(raw):
    """ISO 날짜 문자열을 파싱한다. 비어 있으면 None.

    형식이 잘못된 입력(정상적인 브라우저 제출이 아닌 조작된 요청)도 예외
    없이 None으로 처리한다 — 뒤이은 서비스 계층의 기간 검사는 항상 None
    아니면 유효한 날짜만 받게 된다.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


def _event_edit_form_values_from_event(event):
    return {
        "title": event.title,
        "category": event.category,
        "work_title": event.work_title,
        "location_name": event.location_name,
        "region": event.region,
        "start_date": event.start_date.isoformat() if event.start_date else "",
        "end_date": event.end_date.isoformat() if event.end_date else "",
        "official_url": event.official_url or "",
        "source_name": event.source_name,
        "summary": event.summary,
    }


def _event_edit_form_values_from_post(post_data):
    values = {field: post_data.get(field, "") for field in EVENT_EDIT_TEXT_FIELDS}
    values["start_date"] = post_data.get("start_date", "")
    values["end_date"] = post_data.get("end_date", "")
    return values


@staff_console_required
def staff_event_create(request):
    """새 게시 이벤트를 만든다(GET 빈 폼 / POST-PRG).

    create_published_event를 재사용해 초안 승인 때와 똑같은 제목/공식URL/
    기간 검증 규칙을 적용한다. 생성 성공 시 수정 화면으로 바로 이동시킨다.
    """
    if request.method == "POST":
        form_values = _event_edit_form_values_from_post(request.POST)
        field_errors = {}

        try:
            with transaction.atomic():
                event = create_published_event(
                    title=form_values["title"],
                    category=form_values["category"],
                    work_title=form_values["work_title"],
                    location_name=form_values["location_name"],
                    region=form_values["region"],
                    start_date=_parse_optional_date(form_values["start_date"]),
                    end_date=_parse_optional_date(form_values["end_date"]),
                    official_url=form_values["official_url"],
                    source_name=form_values["source_name"],
                    summary=form_values["summary"],
                )
                StaffActionLog.objects.create(
                    **_action_log_kwargs(
                        _staff_action_metadata(request),
                        StaffActionLog.Action.EVENT_CREATE,
                        target_event=event,
                    )
                )
        except MissingOfficialUrlError:
            field_errors["official_url"] = "공식 URL을 입력해야 합니다."
        except PublishEventTitleError:
            field_errors["title"] = "제목을 입력해야 합니다. (공식 URL과 동일할 수 없습니다.)"
        except DuplicateOfficialUrlError:
            field_errors["official_url"] = "이미 다른 이벤트가 사용 중인 공식 URL입니다."
        except InvalidEventPeriodError:
            field_errors["end_date"] = "종료일은 시작일 이후여야 합니다."
        except PublishEventCategoryError:
            field_errors["category"] = "목록에 없는 카테고리입니다. 다시 선택하세요."
        except PublishEventRegionError:
            field_errors["region"] = "목록에 없는 지역입니다. 다시 선택하세요."
        except PublishEventError:
            field_errors["non_field"] = "생성 중 오류가 발생했습니다. 잠시 후 다시 시도하세요."

        if field_errors:
            return render(
                request,
                "staff/events/create.html",
                {
                    "form_values": form_values,
                    "field_errors": field_errors,
                    "CATEGORY": CATEGORY,
                    "REGION": REGION,
                },
                status=400,
            )

        messages.success(request, "생성되었습니다.")
        return redirect(reverse("staff:event-edit", args=[event.pk]))

    return render(
        request,
        "staff/events/create.html",
        {
            "form_values": EVENT_CREATE_BLANK_FORM_VALUES,
            "field_errors": {},
            "CATEGORY": CATEGORY,
            "REGION": REGION,
        },
    )


@staff_console_required
def staff_event_edit(request, pk):
    """이벤트 필드를 수정한다(GET 폼 / POST-PRG 저장).

    검증 실패 시 DB에 남은 값이 아니라 방금 제출한 값으로 폼을 다시
    그려서, 저장이 거부된 게 데이터 유실처럼 보이지 않게 한다. 게시 상태
    전환과 완전 삭제는 별도 뷰이며, 여기서는 삭제 버튼을 보여줄지 판단할
    수 있도록 archive 참조 개수만 함께 계산해 넘긴다.
    """
    event = get_object_or_404(Event, pk=pk)
    list_query = urlencode(_event_filter_query_pairs(request.GET))
    archive_reference_counts = event_archive_reference_counts(event=event)

    if request.method == "POST":
        form_values = _event_edit_form_values_from_post(request.POST)
        field_errors = {}

        try:
            with transaction.atomic():
                # 동시 수정이 서로 덮어쓰지 않게 저장 경로를 직렬화한다.
                event = get_object_or_404(Event.objects.select_for_update(), pk=pk)
                update_published_event(
                    event=event,
                    title=form_values["title"],
                    category=form_values["category"],
                    work_title=form_values["work_title"],
                    location_name=form_values["location_name"],
                    region=form_values["region"],
                    start_date=_parse_optional_date(form_values["start_date"]),
                    end_date=_parse_optional_date(form_values["end_date"]),
                    official_url=form_values["official_url"],
                    source_name=form_values["source_name"],
                    summary=form_values["summary"],
                )
                StaffActionLog.objects.create(
                    **_action_log_kwargs(
                        _staff_action_metadata(request),
                        StaffActionLog.Action.EVENT_UPDATE,
                        target_event=event,
                    )
                )
        except MissingOfficialUrlError:
            field_errors["official_url"] = "공식 URL을 입력해야 합니다."
        except PublishEventTitleError:
            field_errors["title"] = "제목을 입력해야 합니다. (공식 URL과 동일할 수 없습니다.)"
        except DuplicateOfficialUrlError:
            field_errors["official_url"] = "이미 다른 이벤트가 사용 중인 공식 URL입니다."
        except InvalidEventPeriodError:
            field_errors["end_date"] = "종료일은 시작일 이후여야 합니다."
        except PublishEventCategoryError:
            field_errors["category"] = "목록에 없는 카테고리입니다. 다시 선택하세요."
        except PublishEventRegionError:
            field_errors["region"] = "목록에 없는 지역입니다. 다시 선택하세요."
        except PublishEventError:
            field_errors["non_field"] = "저장 중 오류가 발생했습니다. 잠시 후 다시 시도하세요."

        if field_errors:
            return render(
                request,
                "staff/events/edit.html",
                {
                    "event": event,
                    "form_values": form_values,
                    "field_errors": field_errors,
                    "CATEGORY": CATEGORY,
                    "REGION": REGION,
                    "list_query": list_query,
                    "archive_reference_counts": archive_reference_counts,
                },
                status=400,
            )

        messages.success(request, "저장되었습니다.")
        redirect_url = reverse("staff:event-edit", args=[event.pk])
        if list_query:
            redirect_url = f"{redirect_url}?{list_query}"
        return redirect(redirect_url)

    form_values = _event_edit_form_values_from_event(event)
    return render(
        request,
        "staff/events/edit.html",
        {
            "event": event,
            "form_values": form_values,
            "field_errors": {},
            "CATEGORY": CATEGORY,
            "REGION": REGION,
            "list_query": list_query,
            "archive_reference_counts": archive_reference_counts,
        },
    )


def _reference_block_message(counts):
    return (
        f"찜 {counts['interest']}·상태 {counts['status']}·"
        f"방문기록 {counts['visit']}·컬렉션 {counts['collection_item']}건이 "
        "연결되어 삭제할 수 없습니다."
    )


@staff_console_required
@require_POST
def staff_event_toggle_publish(request, pk):
    """게시 상태를 뒤집는다. 양방향 모두 되돌릴 수 있어 삭제와 달리 확인
    단계가 없다.

    다시 게시할 때는 제목/공식URL 검증을 다시 거친다 — 내려간 동안 상태가
    깨진 이벤트가 검증 없이 조용히 다시 게시되는 것을 막는다.
    """
    list_query = urlencode(_event_filter_query_pairs(request.GET))
    redirect_url = reverse("staff:event-edit", args=[pk])
    if list_query:
        redirect_url = f"{redirect_url}?{list_query}"

    try:
        with transaction.atomic():
            # 토글은 읽은 값을 뒤집는 연산이라, 잠그지 않으면 동시 요청이
            # 같은 상태를 읽고 경쟁한다.
            event = get_object_or_404(Event.objects.select_for_update(), pk=pk)
            if event.publish_status == Event.PublishStatus.PUBLISHED:
                unpublish_event(event=event)
                action = StaffActionLog.Action.EVENT_UNPUBLISH
                success_message = "게시가 내려갔습니다."
            else:
                republish_event(event=event)
                action = StaffActionLog.Action.EVENT_REPUBLISH
                success_message = "다시 게시되었습니다."
            StaffActionLog.objects.create(
                **_action_log_kwargs(
                    _staff_action_metadata(request), action, target_event=event
                )
            )
    except MissingOfficialUrlError:
        messages.error(request, "공식 URL이 없어 다시 게시할 수 없습니다.")
    except PublishEventTitleError:
        messages.error(request, "제목이 없어 다시 게시할 수 없습니다.")
    except DuplicateOfficialUrlError:
        messages.error(request, "다른 이벤트가 이미 이 공식 URL을 사용 중입니다.")
    except InvalidEventPeriodError:
        messages.error(request, "종료일이 시작일보다 빨라 다시 게시할 수 없습니다.")
    except PublishEventCategoryError:
        messages.error(request, "카테고리가 목록에 없는 값이라 다시 게시할 수 없습니다. 먼저 수정하세요.")
    except PublishEventRegionError:
        messages.error(request, "지역이 목록에 없는 값이라 다시 게시할 수 없습니다. 먼저 수정하세요.")
    except PublishEventError:
        messages.error(request, "게시 상태를 변경하는 중 오류가 발생했습니다.")
    else:
        messages.success(request, success_message)

    return redirect(redirect_url)


@staff_console_required
@require_POST
def staff_event_verify(request, pk):
    """이벤트 정보를 재확인했음을 `verified_at`에 기록한다.

    감사 로그도 같은 트랜잭션에서 기록해 로그 실패 시 검증 자체도
    롤백된다. mark_event_verified는 도메인 예외를 던지지 않으므로 except
    분기가 없다.
    """
    event = get_object_or_404(Event, pk=pk)
    list_query = urlencode(_event_filter_query_pairs(request.GET))
    redirect_url = reverse("staff:event-edit", args=[event.pk])
    if list_query:
        redirect_url = f"{redirect_url}?{list_query}"

    with transaction.atomic():
        mark_event_verified(event=event)
        StaffActionLog.objects.create(
            **_action_log_kwargs(
                _staff_action_metadata(request),
                StaffActionLog.Action.EVENT_VERIFY,
                target_event=event,
            )
        )
    messages.success(request, "검증이 완료되었습니다.")

    return redirect(redirect_url)


@staff_console_required
@require_POST
def staff_event_delete(request, pk):
    """이벤트를 완전히 삭제한다. archive 참조가 있으면 막는다.

    서버 렌더링 2단계 확인 절차다: 수정 화면의 삭제 폼이 `confirmed` 없이
    먼저 여기로 오면 확인 화면을 보여주고, 확인 화면의 폼이 다시
    `confirmed=yes`로 요청해야 실제로 지운다. archive 참조 검사는 확인
    화면을 띄우기 전에 먼저 하므로, 어차피 막힐 삭제를 확인하라고 보여주는
    일은 없다.

    감사 로그는 delete_event() 실행 전에, 같은 트랜잭션 안에서
    target_event=event로 기록한다. 삭제가 끝나면 SET_NULL로 이 값도
    비워지므로, 로그를 먼저 남겨야 어떤 이벤트였는지 흔적이 남는다.
    """
    event = get_object_or_404(Event, pk=pk)
    list_query = urlencode(_event_filter_query_pairs(request.GET))
    edit_redirect = reverse("staff:event-edit", args=[event.pk])
    if list_query:
        edit_redirect = f"{edit_redirect}?{list_query}"

    reference_counts = event_archive_reference_counts(event=event)
    if sum(reference_counts.values()) > 0:
        messages.error(request, _reference_block_message(reference_counts))
        return redirect(edit_redirect)

    if request.POST.get("confirmed") != "yes":
        return render(
            request,
            "staff/events/delete_confirm.html",
            {
                "event": event,
                "list_query": list_query,
                "reference_counts": reference_counts,
            },
        )

    try:
        with transaction.atomic():
            StaffActionLog.objects.create(
                **_action_log_kwargs(
                    _staff_action_metadata(request),
                    StaffActionLog.Action.EVENT_DELETE,
                    target_event=event,
                )
            )
            delete_event(event=event)
    except EventHasArchiveReferencesError as exc:
        messages.error(
            request,
            _reference_block_message(
                {
                    "interest": exc.interest_count,
                    "status": exc.status_count,
                    "visit": exc.visit_count,
                    "collection_item": exc.collection_item_count,
                }
            ),
        )
        return redirect(edit_redirect)

    messages.success(request, "삭제되었습니다.")
    list_redirect = reverse("staff:event-list")
    if list_query:
        list_redirect = f"{list_redirect}?{list_query}"
    return redirect(list_redirect)
