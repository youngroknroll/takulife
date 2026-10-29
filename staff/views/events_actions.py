"""이벤트 단건 목표 게시 상태 설정·검증 완료 처리, 일괄 비공개 JSON 엔드포인트.

events.py가 이미 커서(파일 크기 분리 트리거) 근처라 새 엔드포인트 2개와
일괄 비공개 엔드포인트(2026-10-27 events.py에서 이동)는 여기 별도 파일에
둔다. 문구 표·배지 계산은 events.py 소유를 그대로 따르고 이 파일은 그것을
가져다 쓰기만 한다(events_actions → events 단방향).
"""

import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import error_response, field_error_response
from events.models import Event
from events.services import (
    DuplicateOfficialUrlError,
    MissingOfficialUrlError,
    PublishEventError,
    mark_event_verified,
    republish_event,
    unpublish_event,
)
from staff.models import StaffActionLog
from staff.views._helpers import _action_log_kwargs, _staff_action_metadata, _validate_bulk_ids
from staff.views.events import _event_quality_badges, _republish_error_message

logger = logging.getLogger(__name__)


class StaffEventPublishStatusView(APIView):
    """이벤트 하나를 요청받은 목표 게시 상태로 설정한다(토글이 아니다).

    이미 그 상태면 변경·감사 로그 없이 changed=False만 응답해, 응답 유실
    뒤 재시도가 상태를 다시 뒤집지 않는다.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        publish_status = (
            request.data.get("publish_status") if isinstance(request.data, dict) else None
        )
        if publish_status not in Event.PublishStatus.values:
            return field_error_response(
                "publish_status",
                "publish_status must be one of: draft, published.",
            )

        try:
            with transaction.atomic():
                event = get_object_or_404(Event.objects.select_for_update(), pk=pk)
                changed = event.publish_status != publish_status
                if changed:
                    if publish_status == Event.PublishStatus.DRAFT:
                        unpublish_event(event=event)
                        action = StaffActionLog.Action.EVENT_UNPUBLISH
                    else:
                        republish_event(event=event)
                        action = StaffActionLog.Action.EVENT_REPUBLISH
                    StaffActionLog.objects.create(
                        **_action_log_kwargs(
                            _staff_action_metadata(request), action, target_event=event
                        )
                    )
        except (MissingOfficialUrlError, DuplicateOfficialUrlError, PublishEventError) as exc:
            return error_response(_republish_error_message(exc), 400)

        is_published = event.publish_status == Event.PublishStatus.PUBLISHED
        return Response(
            {
                "id": event.id,
                "publish_status": event.publish_status,
                "changed": changed,
                "quality_badges": (
                    _event_quality_badges(event, today=timezone.localdate()) if is_published else []
                ),
            }
        )


class StaffEventVerifiedView(APIView):
    """이벤트를 검증 완료로 기록한다. mark_event_verified는 예외를 던지지 않는다."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        with transaction.atomic():
            event = get_object_or_404(Event, pk=pk)
            mark_event_verified(event=event)
            StaffActionLog.objects.create(
                **_action_log_kwargs(
                    _staff_action_metadata(request),
                    StaffActionLog.Action.EVENT_VERIFY,
                    target_event=event,
                )
            )

        is_published = event.publish_status == Event.PublishStatus.PUBLISHED
        return Response(
            {
                "id": event.id,
                "verified_at": event.verified_at.isoformat(),
                "quality_badges": (
                    _event_quality_badges(event, today=timezone.localdate()) if is_published else []
                ),
            }
        )


MAX_BULK_EVENT_IDS = 20


class StaffEventBulkUnpublishView(APIView):
    """한 요청으로 최대 MAX_BULK_EVENT_IDS개의 이벤트를 비공개로 설정한다.

    토글이 아니라 "목표 상태 설정"이다 — 이미 비공개인 이벤트는 변경·로그
    없이 성공으로 보고한다. 응답 유실 뒤 재시도가 잘못 재게시하는 사고를
    막기 위해서다. 각 id는 독립된 트랜잭션으로 처리돼 한 항목의 실패가
    다른 항목의 성공을 롤백하지 않는다.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        event_ids = body.get("event_ids")
        validation_error = _validate_bulk_ids(
            event_ids, field_name="event_ids", max_items=MAX_BULK_EVENT_IDS
        )
        if validation_error is not None:
            return field_error_response("event_ids", validation_error)

        metadata = _staff_action_metadata(request)
        succeeded = []
        failed = []

        for event_id in event_ids:
            reason = self._unpublish_one(event_id, metadata)
            if reason is None:
                succeeded.append(event_id)
            else:
                failed.append({"id": event_id, "reason": reason})

        return Response({"succeeded": succeeded, "failed": failed}, status=status.HTTP_200_OK)

    @staticmethod
    def _unpublish_one(event_id, metadata):
        """단건 비공개 설정. 성공(또는 이미 비공개)이면 None, 실패하면
        사유 문자열을 반환한다.

        get_object_or_404 대신 select_for_update().get()을 직접 쓴다 —
        Http404를 쓰면 아래 catch-all(Exception)이 그 예외를 삼켜
        "Not found." 계약이 깨진다.
        """
        try:
            with transaction.atomic():
                event = Event.objects.select_for_update().get(pk=event_id)
                if event.publish_status == Event.PublishStatus.PUBLISHED:
                    unpublish_event(event=event)
                    StaffActionLog.objects.create(
                        **_action_log_kwargs(
                            metadata,
                            StaffActionLog.Action.EVENT_UNPUBLISH,
                            target_event=event,
                        )
                    )
        except Event.DoesNotExist:
            return "Not found."
        except Exception:
            # 분류되지 않은 실패라도 배치 나머지를 막지 않는다. 이 시점엔
            # 이 항목의 변경분은 이미 롤백된 상태다. 실제 예외는 로그로
            # 남기고, 클라이언트에는 고정된 문구만 돌려준다.
            logger.exception("bulk unpublish: unexpected error for event_id=%s", event_id)
            return "Unexpected error."
        return None
