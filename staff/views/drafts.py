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
from core.vocab import (
    CATEGORY,
    CATEGORY_LABELS,
    REGION,
    REGION_LABELS,
    is_valid_category,
    is_valid_region,
)
from drafts.labels import REVIEW_STATUS_LABELS
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
from events.models import Event

from ..models import StaffActionLog
from ..search import search_term
from ..permissions import staff_console_required
from ._helpers import _action_log_kwargs, _staff_action_metadata

logger = logging.getLogger(__name__)


def _draft_warning_badges(draft):
    """이미 가져온 필드(제목/지역/기간)만으로 파생하는 경고 태그 목록(B1).

    _event_quality_badges(staff/views/events.py)와 별개다 — 대상이 되는
    모델이 다르고(EventDraft에는 poster_image가 없다) 판정 시점도 다르다
    (게시 전 대기 목록용).
    """
    badges = []
    if not (draft.extracted_title or draft.raw_title):
        badges.append("제목 없음")
    if draft.extracted_region == "":
        badges.append("지역 없음")
    if draft.extracted_start_date is None or draft.extracted_end_date is None:
        badges.append("기간 없음")
    return badges


def _draft_preapproval_checks(draft):
    """승인 전 체크(B2): approve_draft가 실제로 검사하는 불변식을 미리
    보여준다 — 승인 버튼을 눌러 보기 전에 실패 사유를 인스펙터에서 알 수
    있게 한다. key 순서는 approve_draft/create_published_event가 검사하는
    순서를 따른다.
    """
    title_present = bool(draft.extracted_title or draft.raw_title)
    official_url_present = bool(draft.source_url)
    official_url_unique = (
        official_url_present
        and not Event.objects.filter(official_url=draft.source_url).exists()
    )
    return [
        {"key": "title", "label": "제목이 있어야 합니다", "passed": title_present},
        {
            "key": "official_url",
            "label": "공식 URL이 있어야 합니다",
            "passed": official_url_present,
        },
        {
            "key": "official_url_unique",
            "label": "공식 URL이 다른 게시 이벤트와 중복되지 않아야 합니다",
            "passed": official_url_unique,
        },
        {
            "key": "category",
            "label": "카테고리가 목록에 있는 값이어야 합니다",
            "passed": is_valid_category(draft.extracted_category or ""),
        },
        {
            "key": "region",
            "label": "지역이 목록에 있는 값이어야 합니다",
            "passed": is_valid_region(draft.extracted_region or ""),
        },
    ]


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
                "warning_badges": _draft_warning_badges(draft),
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
    search = search_term(request)
    drafts = list_drafts(selected_status, search=search)
    paginator = Paginator(drafts, DRAFT_LISTING_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    draft_rows = _build_draft_rows(page_obj.object_list)

    pager_pairs = [("status", selected_status)] if selected_status else []
    if search:
        pager_pairs.append(("q", search))
    pager_query = "&" + urlencode(pager_pairs) if pager_pairs else ""

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
            "search": search,
            "review_status_labels": REVIEW_STATUS_LABELS,
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
            "preapproval_checks": _draft_preapproval_checks(draft),
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


class StaffDraftBulkRejectView(APIView):
    """한 요청으로 여러 초안을 반려한다(B3). 상한·구조 검증은
    StaffDraftBulkApproveView와 같은 _validate_bulk_draft_ids를 그대로
    쓴다 — 승인과 반려 둘 다 같은 자원(EventDraft)에 대한 같은 크기의
    일괄 쓰기라 상한을 따로 둘 이유가 없다. rejection_reason은 요청
    전체에 하나만 받아 모든 대상에 동일하게 적용한다(단건 반려의
    ``rejection_reason``과 같은 선택 필드, 기본값 "").
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        draft_ids = body.get("draft_ids")
        validation_error = _validate_bulk_draft_ids(draft_ids)
        if validation_error is not None:
            return field_error_response("draft_ids", validation_error)

        rejection_reason = body.get("rejection_reason", "")
        metadata = _staff_action_metadata(request)
        succeeded = []
        failed = []

        for draft_id in draft_ids:
            reason = self._reject_one(draft_id, metadata, rejection_reason)
            if reason is None:
                succeeded.append(draft_id)
            else:
                failed.append({"id": draft_id, "reason": reason})

        return Response({"succeeded": succeeded, "failed": failed}, status=status.HTTP_200_OK)

    @staticmethod
    def _reject_one(draft_id, metadata, rejection_reason):
        """단건 반려. 성공하면 None, 실패하면 사유 문자열을 반환한다.

        분류되지 않은 실패도 배치 나머지를 막지 않는다 —
        StaffDraftBulkApproveView._approve_one과 같은 정책이다.
        """
        try:
            with transaction.atomic():
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
            return "Not found."
        except DraftStateError:
            return "Only pending drafts can be rejected."
        except Exception:
            logger.exception(
                "bulk reject: unexpected error for draft_id=%s", draft_id
            )
            return "Unexpected error."
        return None
