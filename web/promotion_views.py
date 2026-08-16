"""공식 제보 API 엔드포인트 — POST /api/personal-entries/<pk>/promote/.

승격은 archive→drafts를 연결하는데 도메인 경계상 archive 앱 안에서는
이게 금지된다. archive/drafts 양쪽을 모두 볼 수 있는 프레젠테이션·교차도메인
계층인 ``web``이 이 오케스트레이션의 자리다.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.errors import error_response, field_error_response
from web.promotion import (
    PromotionAlreadySubmittedError,
    PromotionDuplicateError,
    PromotionKindNotAllowedError,
    PromotionNotFoundError,
    PromotionUnsafeUrlError,
    promote_personal_entry,
)


class _PromoteSerializer(serializers.Serializer):
    official_url = serializers.URLField(required=True)


class PromotePersonalEntryView(APIView):
    permission_classes = [IsAuthenticated]
    # 관리자 검토 큐가 승격된 드래프트로 폭주하지 않도록 사용자당 일일
    # 상한을 둔다. 속도는 settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]에 있다.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "promotion"

    @extend_schema(
        tags=["collection"],
        summary="비공식 기록을 공식 행사 후보로 제보한다",
        request=_PromoteSerializer,
        responses={
            201: inline_serializer(
                "PromotePersonalEntryResponse",
                {
                    "draft_id": serializers.IntegerField(),
                    "promotion_status": serializers.CharField(),
                },
            ),
            400: OpenApiResponse(
                description="이 항목은 제보할 수 없거나, official_url이 허용되지 않거나 "
                "이미 존재하는 드래프트의 URL과 같다."
            ),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 비공식 기록."),
            409: OpenApiResponse(description="이미 검토 제출된 항목."),
            429: OpenApiResponse(description="일일 제보 상한 초과."),
        },
    )
    def post(self, request, pk):
        serializer = _PromoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = promote_personal_entry(
                user=request.user,
                personal_entry_id=pk,
                official_url=serializer.validated_data["official_url"],
            )
        except PromotionNotFoundError:
            return error_response("Not found.", 404)
        except PromotionKindNotAllowedError:
            return error_response("This item cannot be promoted.", 400)
        except PromotionUnsafeUrlError:
            return field_error_response(
                "official_url", "This URL is not allowed as an official URL."
            )
        except PromotionAlreadySubmittedError:
            return Response(
                {
                    "code": "already_submitted",
                    "detail": "This item has already been submitted for review.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except PromotionDuplicateError:
            return field_error_response(
                "official_url", "A draft with this official URL already exists."
            )

        return Response(
            {"draft_id": result.draft_id, "promotion_status": result.personal_entry.promotion_status},
            status=status.HTTP_201_CREATED,
        )
