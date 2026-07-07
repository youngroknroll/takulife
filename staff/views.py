"""Staff Console views.

PR-2 sub-step D: the 3 draft/home-category SSR views (previously routed
through core.views for a smaller PR-1a diff) now live here permanently,
alongside the draft approve/reject action endpoints. staff -> core is an
allowed presentation-only import (label maps/vocab); core must never import
staff back (see tests/test_architecture_boundaries.py).
"""
import logging
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import error_response, field_error_response
from core.models import HomeConfig
from core.vocab import CATEGORY, CATEGORY_LABELS, REGION, REGION_LABELS
from drafts.models import EventDraft
from drafts.queries import (
    DRAFT_LISTING_PAGE_SIZE,
    draft_review_stats,
    list_draft_sources,
    list_drafts,
)
from drafts.serializers import EventDraftSerializer
from drafts.services import (
    DraftNotFoundError,
    DraftPublicationDuplicateError,
    DraftPublicationError,
    DraftPublicationMissingOfficialUrlError,
    DraftPublicationTitleError,
    DraftStateError,
    approve_draft,
    reject_draft,
)
from events.models import Event
from events.queries import (
    QUALITY_WARNING_KEYS,
    STAFF_EVENT_LISTING_PAGE_SIZE,
    list_staff_events,
    published_quality_warnings,
)

from .models import StaffActionLog
from .permissions import staff_console_required
from .queries import recent_staff_actions

logger = logging.getLogger(__name__)


@staff_console_required
def dashboard(request):
    """Staff console landing page."""
    stats = draft_review_stats()
    return render(
        request,
        "staff/dashboard.html",
        {
            "pending_count": stats["pending"],
            "quality_warnings": published_quality_warnings(),
            "recent_actions": recent_staff_actions(),
            "draft_sources": list_draft_sources(),
        },
    )


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


@staff_console_required
def staff_events(request):
    """Staff console: published+draft event listing with quality-warning drilldown.

    ?warning= is validated against QUALITY_WARNING_KEYS (unknown/blank values
    fall back to "no filter", mirroring event_drafts' selected_status
    normalisation) and links directly from the dashboard's 5 warning rows.
    ?publish_status= is validated against Event.PublishStatus.values the same
    way. Pagination mirrors event_drafts' Paginator usage.
    """
    selected_warning = request.GET.get("warning", "")
    if selected_warning not in QUALITY_WARNING_KEYS:
        selected_warning = ""

    selected_publish_status = request.GET.get("publish_status", "")
    if selected_publish_status not in Event.PublishStatus.values:
        selected_publish_status = ""

    events = list_staff_events(
        warning=selected_warning or None,
        publish_status=selected_publish_status or None,
    )
    paginator = Paginator(events, STAFF_EVENT_LISTING_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    event_rows = _build_event_rows(page_obj.object_list)

    query_pairs = []
    if selected_warning:
        query_pairs.append(("warning", selected_warning))
    if selected_publish_status:
        query_pairs.append(("publish_status", selected_publish_status))
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


def _build_draft_rows(drafts):
    """Attach display labels to each draft for template rendering.

    Returns a list of dicts with the draft object plus resolved
    category_label and region_label so templates use simple dot notation.
    """
    rows = []
    for draft in drafts:
        rows.append(
            {
                "draft": draft,
                "category_label": CATEGORY_LABELS.get(
                    draft.extracted_category, draft.extracted_category
                ),
                "region_label": REGION_LABELS.get(
                    draft.extracted_region, draft.extracted_region
                ),
            }
        )
    return rows


@staff_console_required
@ensure_csrf_cookie
def event_drafts(request):
    selected_status = request.GET.get("status", "")
    if selected_status not in EventDraft.ReviewStatus.values:
        selected_status = ""

    stats = draft_review_stats()
    stats_total = stats["pending"] + stats["approved"] + stats["rejected"]
    drafts = list_drafts(selected_status)
    paginator = Paginator(drafts, DRAFT_LISTING_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    draft_rows = _build_draft_rows(page_obj.object_list)

    pager_query = "&" + urlencode([("status", selected_status)]) if selected_status else ""

    return render(
        request,
        "core/drafts/list.html",
        {
            "draft_rows": draft_rows,
            "stats": stats,
            "stats_total": stats_total,
            "page_obj": page_obj,
            "selected_status": selected_status,
            "pager_query": pager_query,
        },
    )


@staff_console_required
@ensure_csrf_cookie
def event_draft_detail(request, draft_id):
    # Use filter().first() so the staff guard test (which does not seed the DB)
    # still returns 200 (staff can reach the URL). When draft is None the
    # template shows a "not found" notice rather than raising Http404.
    draft = EventDraft.objects.filter(pk=draft_id).first()
    if draft is None:
        return render(
            request,
            "core/drafts/detail.html",
            {
                "draft": None,
                "draft_not_found": True,
                "draft_id": draft_id,
                "CATEGORY": CATEGORY,
                "REGION": REGION,
            },
        )
    is_pending = draft.review_status == EventDraft.ReviewStatus.PENDING
    category_label = CATEGORY_LABELS.get(
        draft.extracted_category, draft.extracted_category
    )
    region_label = REGION_LABELS.get(draft.extracted_region, draft.extracted_region)
    return render(
        request,
        "core/drafts/detail.html",
        {
            "draft": draft,
            "is_pending": is_pending,
            "category_label": category_label,
            "region_label": region_label,
            "CATEGORY": CATEGORY,
            "REGION": REGION,
        },
    )


@staff_console_required
@ensure_csrf_cookie
def staff_home_categories(request):
    """Staff page: select and order the home page category tiles.

    GET  — render a form with current HomeConfig state.
    POST — parse checked/order fields, validate against vocab, save, redirect (PRG).
    """
    config = HomeConfig.get_solo()

    if request.method == "POST":
        checked = []
        for slug, _ in CATEGORY:
            if request.POST.get(f"feature_{slug}") == "on":
                try:
                    order = int(request.POST.get(f"order_{slug}", "0"))
                except (ValueError, TypeError):
                    order = 9999  # Safe fallback: append to end
                checked.append((slug, order))

        checked.sort(key=lambda pair: pair[1])
        config.featured_categories = [slug for slug, _ in checked]

        with transaction.atomic():
            config.save()
            StaffActionLog.objects.create(
                actor=request.user,
                action=StaffActionLog.Action.HOME_CATEGORIES,
                target_draft=None,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

        messages.success(request, "카테고리 설정이 저장되었습니다.")
        return redirect("staff:home-categories")

    # GET: build form rows — one per vocab category, with current state
    featured_set = set(config.featured_categories)
    featured_order = {slug: idx + 1 for idx, slug in enumerate(config.featured_categories)}

    category_rows = [
        {
            "slug": slug,
            "label": label,
            "checked": slug in featured_set,
            "order": featured_order.get(slug, vocab_idx + 1),
        }
        for vocab_idx, (slug, label) in enumerate(CATEGORY)
    ]

    return render(
        request,
        "core/staff/home_categories.html",
        {
            "category_rows": category_rows,
            "config": config,
        },
    )


def _staff_action_metadata(request):
    """Extract actor/ip/user-agent for a StaffActionLog entry from the request."""
    return {
        "actor": request.user,
        "ip_address": request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
    }


class StaffDraftApproveView(APIView):
    """Approve a pending draft and publish it as an Event.

    Same request/response contract as the former
    drafts.views.AdminEventDraftApproveView. The audit log write happens at
    this view boundary, inside an OUTER transaction.atomic() that wraps the
    service call's own (inner) atomic block — if the log write fails, the
    whole approval (including the published Event) rolls back too.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, draft_id):
        metadata = _staff_action_metadata(request)

        try:
            with transaction.atomic():
                result = approve_draft(draft_id, actor=metadata["actor"])
                StaffActionLog.objects.create(
                    actor=metadata["actor"],
                    action=StaffActionLog.Action.APPROVE,
                    target_draft=result.draft,
                    ip_address=metadata["ip_address"],
                    user_agent=metadata["user_agent"],
                )
        except DraftNotFoundError:
            return error_response("Not found.", 404)
        except DraftStateError:
            return error_response("Only pending drafts can be approved.", 400)
        except DraftPublicationDuplicateError:
            return field_error_response(
                "official_url", "Event with this official URL already exists."
            )
        except DraftPublicationMissingOfficialUrlError:
            return field_error_response(
                "official_url", "Official URL is required for publication."
            )
        except DraftPublicationTitleError:
            return field_error_response("title", "제목을 입력해야 게시할 수 있습니다.")
        except DraftPublicationError:
            return error_response("Event publication failed.", 503)

        data = {**EventDraftSerializer(result.draft).data, "event_id": result.event_id}
        return Response(data, status=status.HTTP_200_OK)


MAX_BULK_APPROVE_DRAFT_IDS = 20


def _validate_bulk_draft_ids(draft_ids):
    """Return an error message if draft_ids fails structural validation, else None.

    Structural-only: whether each id actually exists/is pending is decided
    per-item inside the view's loop, not here.
    """
    if not isinstance(draft_ids, list) or not draft_ids:
        return "draft_ids must be a non-empty list."
    # Cap check runs before the per-item scan so an oversized payload is
    # rejected without a full O(n) integer-type scan first.
    if len(draft_ids) > MAX_BULK_APPROVE_DRAFT_IDS:
        return f"draft_ids must contain at most {MAX_BULK_APPROVE_DRAFT_IDS} ids."
    if not all(
        isinstance(draft_id, int) and not isinstance(draft_id, bool)
        for draft_id in draft_ids
    ):
        return "draft_ids must contain only integers."
    return None


class StaffDraftBulkApproveView(APIView):
    """Approve up to MAX_BULK_APPROVE_DRAFT_IDS pending drafts in one request.

    Each id is processed independently, in its own outer-atomic block — the
    same approve_draft() + StaffActionLog.objects.create() pairing as
    StaffDraftApproveView, repeated per item. One item's failure never rolls
    back another's success. The response is always 200 (partial success is
    the normal case, not an error); 400 is reserved for requests that are
    structurally invalid before any item is touched (see
    _validate_bulk_draft_ids).
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        draft_ids = body.get("draft_ids")
        validation_error = _validate_bulk_draft_ids(draft_ids)
        if validation_error is not None:
            return field_error_response("draft_ids", validation_error)

        metadata = _staff_action_metadata(request)
        succeeded = []
        failed = []

        for draft_id in draft_ids:
            reason = self._approve_one(draft_id, metadata)
            if reason is None:
                succeeded.append(draft_id)
            else:
                failed.append({"id": draft_id, "reason": reason})

        return Response({"succeeded": succeeded, "failed": failed}, status=status.HTTP_200_OK)

    @staticmethod
    def _approve_one(draft_id, metadata):
        """Approve a single draft. Return None on success, else a failure reason.

        Mirrors StaffDraftApproveView's per-item outer-atomic pattern: the
        StaffActionLog write is inside the same transaction.atomic() block as
        the approve_draft() call, so a log-write failure rolls back that
        item's approval too, without touching any other item.
        """
        try:
            with transaction.atomic():
                result = approve_draft(draft_id, actor=metadata["actor"])
                StaffActionLog.objects.create(
                    actor=metadata["actor"],
                    action=StaffActionLog.Action.APPROVE,
                    target_draft=result.draft,
                    ip_address=metadata["ip_address"],
                    user_agent=metadata["user_agent"],
                )
        except DraftNotFoundError:
            return "Not found."
        except DraftStateError:
            return "Only pending drafts can be approved."
        except DraftPublicationDuplicateError:
            return "Event with this official URL already exists."
        except DraftPublicationMissingOfficialUrlError:
            return "Official URL is required for publication."
        except DraftPublicationTitleError:
            return "제목을 입력해야 게시할 수 있습니다."
        except DraftPublicationError:
            return "Event publication failed."
        except Exception:
            # Catch-all so one item's unclassified failure (e.g. a log-write
            # IntegrityError) never aborts the rest of the batch — the
            # transaction.atomic() block above has already rolled back this
            # item's own changes by the time control reaches here. Log the
            # real exception (see events/services.py convention) while still
            # returning the same static client-facing reason.
            logger.exception(
                "bulk approve: unexpected error for draft_id=%s", draft_id
            )
            return "Unexpected error."
        return None


class StaffDraftRejectView(APIView):
    """Reject a pending draft.

    Same request/response contract as the former
    drafts.views.AdminEventDraftRejectView. See StaffDraftApproveView for the
    outer-atomic audit log rationale.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, draft_id):
        metadata = _staff_action_metadata(request)

        try:
            with transaction.atomic():
                # Intentional v1 scope: no rejection_reason passed here — the
                # client (draft.js) posts an empty body and has no reason
                # input wired up yet. The service supports rejection_reason=
                # for a future step.
                draft = reject_draft(draft_id, actor=metadata["actor"])
                StaffActionLog.objects.create(
                    actor=metadata["actor"],
                    action=StaffActionLog.Action.REJECT,
                    target_draft=draft,
                    ip_address=metadata["ip_address"],
                    user_agent=metadata["user_agent"],
                )
        except DraftNotFoundError:
            return error_response("Not found.", 404)
        except DraftStateError:
            return error_response("Only pending drafts can be rejected.", 400)

        return Response(EventDraftSerializer(draft).data, status=status.HTTP_200_OK)
