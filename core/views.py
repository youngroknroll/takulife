"""인프라 헬스체크와 API 루트 뷰. 도메인 결합이 없다."""
from django.db import OperationalError, connection
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def api_root(request):
    return Response({"name": "takulife API"})


@api_view(["GET"])
def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return Response({"status": "error"}, status=503)
    return Response({"status": "ok"})
