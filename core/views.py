"""인프라 헬스체크와 API 루트 뷰. 도메인 결합이 없다."""
from django.db import OperationalError, connection
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def api_root(request):
    return Response({"name": "takulife API"})


def robots_txt(request):
    # 베타 준비 중 실사용자 유입을 막는 기술적 담보. 정식 런치 때 해제해야
    # 한다(docs/deploy-runbook.md §3 체크리스트 12번).
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


@api_view(["GET"])
def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return Response({"status": "error"}, status=503)
    return Response({"status": "ok"})
