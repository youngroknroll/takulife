"""Staff Console views: published+draft event CRUD and quality drilldown."""
import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import serializers

from core.vocab import CATEGORY, CATEGORY_LABELS, REGION, REGION_LABELS
from events.image_validation import validate_uploaded_image
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
    clear_event_poster,
    create_published_event,
    republish_event,
    set_event_poster,
    unpublish_event,
    update_published_event,
)

from ..models import StaffActionLog
from ..permissions import staff_console_required
from ..services import (
    EventHasArchiveReferencesError,
    delete_event,
    event_archive_reference_counts,
)
from ._helpers import _action_log_kwargs, _staff_action_metadata

# Korean labels for the 5 QUALITY_WARNING_KEYS, shared by the filter chips
# and the per-row quality badges below. Mirrors the strings already used in
# staff/dashboard.html's warning table (kept in sync manually — both are
# small, static, single-consumer label sets).
QUALITY_WARNING_LABELS = {
    "missing_official_url": "공식 URL 없음",
    "ended_still_published": "종료됐지만 게시 중",
    "missing_poster": "포스터 없음",
    "missing_dates": "날짜 정보 누락",
    "missing_region": "지역 정보 없음",
}


def _event_quality_badges(event, *, today):
    """Return the Korean warning labels this event trips, or [] if none.

    Mirrors the 5 predicates in events.queries exactly. Only called for
    published events in _build_event_rows — the predicates (and the
    dashboard counts they mirror) are published-scoped, so a draft event
    always gets an empty badge list rather than a misleading one.
    """
    badges = []
    if not event.official_url:
        badges.append(QUALITY_WARNING_LABELS["missing_official_url"])
    if event.end_date and event.end_date < today:
        badges.append(QUALITY_WARNING_LABELS["ended_still_published"])
    if not event.poster_image:
        badges.append(QUALITY_WARNING_LABELS["missing_poster"])
    if event.start_date is None or event.end_date is None:
        badges.append(QUALITY_WARNING_LABELS["missing_dates"])
    if event.region == "":
        badges.append(QUALITY_WARNING_LABELS["missing_region"])
    return badges


def _build_event_rows(events):
    """Attach display labels + quality badges to each event for the template."""
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
    """Validate ?warning=/?publish_status= against their whitelists.

    Shared by staff_events (list) and staff_event_edit (filter-preserving
    "back to list" link) so both normalise unknown/blank values the same way
    — unknown values fall back to "no filter" (mirrors event_drafts'
    selected_status normalisation).
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
    """Staff console: published+draft event listing with quality-warning drilldown.

    ?warning= is validated against QUALITY_WARNING_KEYS (unknown/blank values
    fall back to "no filter", mirroring event_drafts' selected_status
    normalisation) and links directly from the dashboard's 5 warning rows.
    ?publish_status= is validated against Event.PublishStatus.values the same
    way. Pagination mirrors event_drafts' Paginator usage.
    """
    selected_warning, selected_publish_status = _selected_event_filters(request.GET)

    events = list_staff_events(
        warning=selected_warning or None,
        publish_status=selected_publish_status or None,
    )
    paginator = Paginator(events, STAFF_EVENT_LISTING_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    event_rows = _build_event_rows(page_obj.object_list)

    query_pairs = _event_filter_query_pairs(request.GET)
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
    """Parse an ISO date string from a <input type="date">, or None if blank.

    Malformed input (a tampered request, not a normal browser submission)
    is treated as blank rather than raising — the service-level period check
    that follows only ever sees None or a real date.
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
    """Staff console: create a new published event (GET blank form / POST-PRG).

    Reuses create_published_event — the shared publish choke-point already
    used by drafts.services.approve_draft — so a staff-created event has the
    exact same title/official_url/period invariants and unique constraint as
    an approved draft. No poster field here: a poster can only be attached
    to a saved event, so the operator is redirected straight to the edit
    page (which already owns poster upload) on success.
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
    """Staff console: edit a single event's fields (GET form / POST-PRG save).

    Delegates the title/official_url/period invariants to
    events.services.update_published_event and maps its domain errors to
    field-level messages, re-rendering the page with the operator's POSTed
    values (not the stale DB values) so a rejected save never looks like
    silent data loss. Poster upload/removal reuses the existing
    set_event_poster/clear_event_poster services and their shared image
    validation. The publish-status toggle and hard delete are separate POST
    forms/views (staff_event_toggle_publish / staff_event_delete) — this view
    only computes the archive reference counts so the template can show the
    delete button (0 references) or a static "N건 연결되어 삭제할 수 없습니다"
    notice (1+) in their place.
    """
    event = get_object_or_404(Event, pk=pk)
    list_query = urlencode(_event_filter_query_pairs(request.GET))
    archive_reference_counts = event_archive_reference_counts(event=event)

    if request.method == "POST":
        form_values = _event_edit_form_values_from_post(request.POST)
        field_errors = {}

        poster_file = request.FILES.get("poster")
        clear_poster = request.POST.get("clear_poster") == "on"
        validated_poster = None
        if poster_file is not None:
            try:
                validated_poster = validate_uploaded_image(poster_file)
            except serializers.ValidationError as exc:
                detail = exc.detail
                field_errors["poster"] = str(detail[0] if isinstance(detail, list) else detail)

        if not field_errors:
            try:
                with transaction.atomic():
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

        if clear_poster:
            clear_event_poster(event=event)
        elif validated_poster is not None:
            set_event_poster(event=event, image=validated_poster)

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
    """Staff console: flip a published event to draft ("게시 내리기") or a
    draft event back to published ("다시 게시"). Reversible either way — no
    confirmation step, unlike the delete view below.

    Republishing re-validates the title/official_url invariants (see
    events.services.republish_event) so an event that was left in a broken
    state while unpublished cannot silently re-enter the published set.
    """
    event = get_object_or_404(Event, pk=pk)
    list_query = urlencode(_event_filter_query_pairs(request.GET))
    redirect_url = reverse("staff:event-edit", args=[event.pk])
    if list_query:
        redirect_url = f"{redirect_url}?{list_query}"

    try:
        with transaction.atomic():
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
def staff_event_delete(request, pk):
    """Staff console: hard-delete an event, guarded by archive references.

    A 2-step server-rendered confirmation (no new JS file — see
    prompt_plan.md's "하지 말 것"): the edit page's delete form POSTs here
    without `confirmed`, this view re-renders a dedicated confirmation page,
    and that page's own form POSTs back here with `confirmed=yes` to finish
    the delete. Archive references are checked before the confirmation page
    is even shown, so an operator is never invited to confirm a delete that
    is going to be rejected anyway.

    The audit log is written with target_event=event *before* delete_event()
    runs, inside the same transaction — Event's on_delete=SET_NULL then nulls
    this same row out as part of the delete collector's own work, leaving an
    action+actor-only record (no title snapshot field exists on
    StaffActionLog, and this PR does not add one).
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
