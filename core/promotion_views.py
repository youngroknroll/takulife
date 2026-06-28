"""API endpoint for 공식 제보 — POST /api/personal-entries/<pk>/promote/.

Lives in ``core`` (not ``archive``) because promotion bridges archive→drafts,
which the domain boundary forbids inside the archive app itself.
"""
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.errors import error_response, field_error_response
from core.promotion import (
    PromotionAlreadySubmittedError,
    PromotionDuplicateError,
    PromotionNotFoundError,
    promote_personal_entry,
)


class _PromoteSerializer(serializers.Serializer):
    official_url = serializers.URLField(required=True)


class PromotePersonalEntryView(APIView):
    permission_classes = [IsAuthenticated]
    # Per-user daily cap so the admin review queue can't be flooded with
    # promoted drafts. Rate lives in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "promotion"

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
