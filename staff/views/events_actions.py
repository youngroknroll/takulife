"""이벤트 단건 목표 게시 상태 설정·검증 완료 처리 JSON 엔드포인트.

events.py가 이미 커서(파일 크기 분리 트리거) 근처라 새 엔드포인트 2개는
여기 별도 파일에 둔다. 문구 표·배지 계산은 events.py 소유를 그대로 따르고
이 파일은 그것을 가져다 쓰기만 한다(events_actions → events 단방향).
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
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

from ..models import StaffActionLog
from ._helpers import _action_log_kwargs, _staff_action_metadata
from .events import _event_quality_badges, _republish_error_message


class StaffEventPublishStatusView(APIView):
    """이벤트 하나를 요청받은 목표 게시 상태로 설정한다(토글이 아니다).

    이미 그 상태면 변경·감사 로그 없이 changed=False만 응답해, 응답 유실
    뒤 재시도가 상태를 다시 뒤집지 않는다.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        publish_status = request.data.get("publish_status") if isinstance(request.data, dict) else None
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
                    _event_quality_badges(event, today=timezone.localdate())
                    if is_published
                    else []
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
                    _event_quality_badges(event, today=timezone.localdate())
                    if is_published
                    else []
                ),
            }
        )
