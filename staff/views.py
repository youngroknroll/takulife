"""Staff Console views.

PR-2 sub-step D: the 3 draft/home-category SSR views (previously routed
through core.views for a smaller PR-1a diff) now live here permanently,
alongside the draft approve/reject action endpoints. staff -> core is an
allowed presentation-only import (label maps/vocab); core must never import
staff back (see tests/test_architecture_boundaries.py).
"""
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import error_response, field_error_response
from core.models import HomeConfig
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
from events.queries import published_quality_warnings

from .models import StaffActionLog
from .permissions import staff_console_required
from .queries import recent_staff_actions


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
