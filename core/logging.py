"""core/logging.py — 처리되지 않은 뷰 예외를 오류 묶음으로 남기는 핸들러.

`django.request` 로거에만 붙는다(root 금지) — 그래야 500 로그만 잡고 다른
경로의 의도된 warning까지 오류 묶음으로 새지 않는다.
"""
import logging


class ErrorGroupHandler(logging.Handler):
    """settings.LOGGING이 앱 레지스트리 준비 전에 이 클래스를 임포트하므로
    모듈 최상단에 Django 모델·앱 임포트를 두지 않는다 — emit() 안에서만
    지연 임포트한다."""

    def emit(self, record):
        if not record.exc_info:
            return

        exc = record.exc_info[1]

        from django.db import Error as DatabaseError

        if isinstance(exc, DatabaseError):
            # DB 장애 중에 오류 묶음을 남기려고 DB에 또 접근하면 지연이
            # 늘어나 gunicorn 워커 타임아웃을 부를 수 있다 — 건너뛴다.
            return

        request = getattr(record, "request", None)
        method = getattr(request, "method", "")
        resolver_match = getattr(request, "resolver_match", None)
        route = getattr(resolver_match, "route", None) or "unresolved"
        location = f"{method} {route}".strip()

        from core.error_groups import record_error

        # record_error는 절대 예외를 던지지 않는다(자체 except-ok 보장) —
        # 여기서 다시 감싸면 그 보장이 깨져도 못 잡아낸다.
        record_error(
            source="backend",
            error_type=type(exc).__qualname__,
            location=location,
            message=str(exc),
        )
