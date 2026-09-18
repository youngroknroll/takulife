"""운영 데이터 보존 정리.

대상마다 (건수 조회, 삭제) 함수 쌍을 두고 표로 나열한 뒤 순서대로 도는
이유는, 하나가 실패해도 나머지 대상은 계속 처리되게 격리하기 위해서다
(트랙 37 S1). 실패는 예외를 삼키지 않고 로그로 남긴다.
"""
import logging
from datetime import timedelta

from axes.handlers.proxy import AxesProxyHandler
from axes.models import AccessFailureLog, AccessLog
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.utils import timezone

from core.error_groups import prune_stale_error_groups

logger = logging.getLogger(__name__)


def _count_sessions(days):
    return Session.objects.filter(expire_date__lt=timezone.now()).count()


def _delete_sessions(days):
    count = _count_sessions(days)
    call_command("clearsessions")
    return count


def _count_access_logs(days):
    limit = timezone.now() - timedelta(days=days)
    return AccessLog.objects.filter(attempt_time__lte=limit).count()


def _delete_access_logs(days):
    return AxesProxyHandler.reset_logs(age_days=days)


def _count_access_failure_logs(days):
    limit = timezone.now() - timedelta(days=days)
    return AccessFailureLog.objects.filter(attempt_time__lte=limit).count()


def _delete_access_failure_logs(days):
    return AxesProxyHandler.reset_failure_logs(age_days=days)


def _count_error_groups(days):
    return prune_stale_error_groups(days=days, dry_run=True)


def _delete_error_groups(days):
    return prune_stale_error_groups(days=days, dry_run=False)


# 순서가 그대로 보고 순서다(명령의 stdout 출력이 이 순서를 따른다).
_TARGETS = (
    ("sessions", _count_sessions, _delete_sessions),
    ("access_logs", _count_access_logs, _delete_access_logs),
    ("access_failure_logs", _count_access_failure_logs, _delete_access_failure_logs),
    ("error_groups", _count_error_groups, _delete_error_groups),
)


def prune_operational_data(*, days=90, dry_run=False):
    """대상별로 만료·보존 기간이 지난 운영 로그성 데이터를 정리한다."""
    results = {}

    for key, count_fn, delete_fn in _TARGETS:
        count = None
        try:
            count = count_fn(days)
            deleted = 0 if dry_run else delete_fn(days)
            results[key] = {"count": count, "deleted": deleted, "error": None}
        except Exception as exc:
            logger.exception("retention target failed: %s", key)
            results[key] = {"count": count, "deleted": 0, "error": type(exc).__name__}

    return results
