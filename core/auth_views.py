from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@extend_schema(
    tags=["core"],
    summary="현재 로그인한 사용자 정보를 조회한다",
    responses={
        200: inline_serializer(
            "AuthMeResponse",
            {
                "id": serializers.IntegerField(),
                "email": serializers.EmailField(),
                "is_staff": serializers.BooleanField(),
            },
        ),
        403: OpenApiResponse(description="인증되지 않은 요청."),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response(
        {
            "id": user.id,
            "email": user.email,
            "is_staff": user.is_staff,
        }
    )
