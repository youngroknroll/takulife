"""DRF 예외 응답의 언어 무관 code — 클라이언트가 번역된 detail 문구로
인증 필요 여부를 판별하지 않도록 고정된 code를 함께 싣는다."""
from rest_framework.exceptions import NotAuthenticated
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(exc, NotAuthenticated):
        response.data = {**response.data, "code": "not_authenticated"}
    return response
