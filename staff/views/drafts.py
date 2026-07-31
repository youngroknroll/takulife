"""스태프 콘솔 뷰: 초안 목록/상세 화면과 승인/반려(단건+일괄) 엔드포인트."""
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
from ._helpers import _action_log_kwargs, _staff_action_metadata

logger = logging.getLogger(__name__)


def _build_draft_rows(drafts):
    """템플릿이 점 표기법만으로 쓸 수 있도록 카테고리/지역 라벨을 붙인다."""
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
    # get_object_or_404 대신 filter().first()를 써서, draft가 없어도
    # 404를 던지지 않고 템플릿이 "찾을 수 없음" 안내를 보여주게 한다.
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


class StaffDraftApproveView(APIView):
    """대기 중인 초안을 승인하고 Event로 게시한다.

    감사 로그 기록은 서비스 호출의 내부 atomic 블록을 감싸는 바깥쪽
    transaction.atomic() 안에서 이뤄진다 — 로그 기록이 실패하면 방금
    게시한 Event를 포함해 승인 전체가 롤백된다.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, draft_id):
        metadata = _staff_action_metadata(request)

        try:
            with transaction.atomic():
                result = approve_draft(draft_id=draft_id, actor=metadata["actor"])
                StaffActionLog.objects.create(
                    **_action_log_kwargs(
                        metadata, StaffActionLog.Action.APPROVE, target_draft=result.draft
                    )
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
    """구조만 검사한다. 각 id가 실제 존재/대기 상태인지는 뷰의 반복문에서
    항목별로 판단한다."""
    if not isinstance(draft_ids, list) or not draft_ids:
        return "draft_ids must be a non-empty list."
    # 개수 상한 검사를 먼저 해서, 과도하게 큰 payload는 전체를 훑기 전에 걸러낸다.
    if len(draft_ids) > MAX_BULK_APPROVE_DRAFT_IDS:
        return f"draft_ids must contain at most {MAX_BULK_APPROVE_DRAFT_IDS} ids."
    if not all(
        isinstance(draft_id, int) and not isinstance(draft_id, bool)
        for draft_id in draft_ids
    ):
        return "draft_ids must contain only integers."
    return None


class StaffDraftBulkApproveView(APIView):
    """한 요청으로 최대 MAX_BULK_APPROVE_DRAFT_IDS개의 초안을 승인한다.

    각 id는 독립된 트랜잭션으로 처리돼 한 항목의 실패가 다른 항목의
    성공을 롤백하지 않는다. 부분 성공이 정상 케이스라 응답은 항상 200이고,
    400은 요청 자체가 구조적으로 잘못됐을 때만 쓴다.
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
        """단건 승인. 성공하면 None, 실패하면 사유 문자열을 반환한다.

        StaffActionLog 기록이 approve_draft()와 같은 transaction.atomic()
        안에 있어, 로그 기록 실패가 이 항목만 롤백시키고 다른 항목에는
        영향을 주지 않는다.
        """
        try:
            with transaction.atomic():
                result = approve_draft(draft_id=draft_id, actor=metadata["actor"])
                StaffActionLog.objects.create(
                    **_action_log_kwargs(
                        metadata, StaffActionLog.Action.APPROVE, target_draft=result.draft
                    )
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
            # 분류되지 않은 실패라도 배치 나머지를 막지 않는다. 이 시점엔
            # 이 항목의 변경분은 이미 롤백된 상태다. 실제 예외는 로그로
            # 남기고, 클라이언트에는 고정된 문구만 돌려준다.
            logger.exception(
                "bulk approve: unexpected error for draft_id=%s", draft_id
            )
            return "Unexpected error."
        return None


class StaffDraftRejectView(APIView):
    """대기 중인 초안을 반려한다. 감사 로그의 트랜잭션 구조는
    StaffDraftApproveView와 같다."""

    permission_classes = [IsAdminUser]

    def post(self, request, draft_id):
        metadata = _staff_action_metadata(request)

        try:
            with transaction.atomic():
                # rejection_reason은 선택 항목이라 기본값 ""로 기존 빈-본문
                # 요청과의 호환을 유지한다.
                rejection_reason = request.data.get("rejection_reason", "")
                draft = reject_draft(
                    draft_id=draft_id,
                    actor=metadata["actor"],
                    rejection_reason=rejection_reason,
                )
                StaffActionLog.objects.create(
                    **_action_log_kwargs(
                        metadata, StaffActionLog.Action.REJECT, target_draft=draft
                    )
                )
        except DraftNotFoundError:
            return error_response("Not found.", 404)
        except DraftStateError:
            return error_response("Only pending drafts can be rejected.", 400)

        return Response(EventDraftSerializer(draft).data, status=status.HTTP_200_OK)
