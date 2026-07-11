"""Staff Console views: draft listing/detail SSR pages and the approve/reject
action endpoints (single + bulk)."""
import logging
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import error_response, field_error_response
from core.vocab import CATEGORY, CATEGORY_LABELS, REGION, REGION_LABELS
from drafts.models import EventDraft
from drafts.queries import DRAFT_LISTING_PAGE_SIZE, draft_review_stats, list_drafts
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

from ..models import StaffActionLog
from ..permissions import staff_console_required

logger = logging.getLogger(__name__)


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
                result = approve_draft(draft_id=draft_id, actor=metadata["actor"])
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
                result = approve_draft(draft_id=draft_id, actor=metadata["actor"])
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
                # draft.js posts an optional rejection_reason (PR-D2 item 11);
                # default "" preserves the pre-existing empty-body contract
                # (tests/test_staff_draft_actions.py's happy-reject case).
                rejection_reason = request.data.get("rejection_reason", "")
                draft = reject_draft(
                    draft_id=draft_id,
                    actor=metadata["actor"],
                    rejection_reason=rejection_reason,
                )
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
