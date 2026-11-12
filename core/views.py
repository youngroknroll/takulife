"""인프라 헬스체크와 API 루트 뷰. 도메인 결합이 없다."""

import time

from django.db import OperationalError, connection
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

# 마지막으로 DB 확인에 성공한 시각을 워커 메모리에 둔다.
_last_db_check_at = None

# 헬스 체크가 5초마다 오므로 DB 확인은 30분에 한 번만 한다.
HEALTH_DB_CHECK_INTERVAL_SECONDS = 30 * 60


def _db_check_is_due():
    if _last_db_check_at is None:
        return True
    return time.monotonic() - _last_db_check_at >= HEALTH_DB_CHECK_INTERVAL_SECONDS


@extend_schema(
    tags=["core"],
    summary="API 루트 정보를 조회한다",
    responses=inline_serializer("ApiRootResponse", {"name": serializers.CharField()}),
)
@api_view(["GET"])
def api_root(request):
    return Response({"name": "takulife API"})


def robots_txt(request):
    # 비제품 경로와 달력·이벤트 목록의 쿼리 주소를 막는다. 이전·다음 달 링크와
    # 필터·정렬·페이지 조합이 끝없이 이어져 크롤러가 계속 따라가기 때문이다.
    # 앞 2줄은 와일드카드를 모르는 크롤러용이다.
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    return HttpResponse(
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /api/\n"
        "Disallow: /accounts/\n"
        "Disallow: /staff/\n"
        "Disallow: /events/?\n"
        "Disallow: /events/calendar/?\n"
        "Disallow: /?month=\n"
        "Disallow: /*?month=\n"
        "Disallow: /*&month=\n"
        "Disallow: /*?date=\n"
        "Disallow: /*&date=\n"
        f"Sitemap: {sitemap_url}\n",
        content_type="text/plain",
    )


@extend_schema(
    tags=["core"],
    summary="서버 상태를 확인한다(DB 연결은 30분에 한 번 확인한다)",
    responses={
        200: inline_serializer("HealthOkResponse", {"status": serializers.CharField()}),
        503: inline_serializer("HealthErrorResponse", {"status": serializers.CharField()}),
    },
)
@api_view(["GET"])
def health(request):
    global _last_db_check_at
    if _db_check_is_due():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except OperationalError:
            return Response({"status": "error"}, status=503)
        _last_db_check_at = time.monotonic()
    return Response({"status": "ok"})
