"""도메인 결합이 없는 정적 페이지와 인프라 헬스체크 뷰."""
from django.db import OperationalError, connection
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response


def legal_privacy(request):
    return render(request, "core/legal/privacy.html")


def legal_terms(request):
    return render(request, "core/legal/terms.html")


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
