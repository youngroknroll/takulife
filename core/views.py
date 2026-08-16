"""인프라 헬스체크와 API 루트 뷰. 도메인 결합이 없다."""
from django.db import OperationalError, connection
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response


@extend_schema(
    tags=["core"],
    summary="API 루트 정보를 조회한다",
    responses=inline_serializer("ApiRootResponse", {"name": serializers.CharField()}),
)
@api_view(["GET"])
def api_root(request):
    return Response({"name": "takulife API"})


def robots_txt(request):
    # 베타 준비 중 실사용자 유입을 막는 기술적 담보. 정식 런치 때 해제해야
    # 한다(docs/deploy-runbook.md §3 체크리스트 12번).
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


@extend_schema(
    tags=["core"],
    summary="데이터베이스 연결 상태를 확인한다",
    responses={
        200: inline_serializer("HealthOkResponse", {"status": serializers.CharField()}),
        503: inline_serializer("HealthErrorResponse", {"status": serializers.CharField()}),
    },
)
@api_view(["GET"])
def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return Response({"status": "error"}, status=503)
    return Response({"status": "ok"})
