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
    # 비제품 경로만 차단하고 나머지 전체 크롤링은 허용한다.
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    return HttpResponse(
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /api/\n"
        "Disallow: /accounts/\n"
        "Disallow: /staff/\n"
        f"Sitemap: {sitemap_url}\n",
        content_type="text/plain",
    )


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
