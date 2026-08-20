"""탐색 실행(run)·러너 heartbeat·임대 수명주기를 소유하는 서비스 계층."""
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from drafts.models import DiscoveryRunnerStatus, SourceCandidate, SourceDiscoveryRun

# 러너 폴링 주기에 여유를 둔 신선도 기준(초).
HEARTBEAT_FRESH_SECONDS = 120

# 에이전트 웹 탐색이 몇 분 걸릴 수 있어 여유를 둔 임대 시간(초).
LEASE_SECONDS = 900

# 최초 1회 + 재시도 1회까지만 재임대(정본 재시도 상한 결정).
MAX_LEASES = 2

# 러너가 보낸 원문 사유를 그대로 노출하지 않기 위한 허용 목록(보안 계약).
_ALLOWED_FAILURE_KINDS = {"agent_error", "agent_timeout", "invalid_output"}


class RunnerOfflineError(Exception):
    pass


class DiscoveryRunActiveError(Exception):
    pass


class LeaseInvalidError(Exception):
    pass


def runner_is_online(*, status_row):
    """DiscoveryRunnerStatus 행(없으면 None)을 받아 신선도 판정을 소유한다."""
    if status_row is None:
        return False
    return status_row.last_heartbeat_at >= timezone.now() - timedelta(
        seconds=HEARTBEAT_FRESH_SECONDS
    )


def record_heartbeat(*, provider):
    DiscoveryRunnerStatus.objects.update_or_create(
        pk=1, defaults={"last_heartbeat_at": timezone.now(), "provider": provider}
    )


def create_run(*, requested_by):
    status = DiscoveryRunnerStatus.objects.filter(pk=1).first()
    if status is None or status.last_heartbeat_at < timezone.now() - timedelta(
        seconds=HEARTBEAT_FRESH_SECONDS
    ):
        raise RunnerOfflineError

    active_statuses = [SourceDiscoveryRun.Status.PENDING, SourceDiscoveryRun.Status.CLAIMED]
    if SourceDiscoveryRun.objects.filter(status__in=active_statuses).exists():
        raise DiscoveryRunActiveError

    return SourceDiscoveryRun.objects.create(requested_by=requested_by)


def claim(*, provider):
    with transaction.atomic():
        # 별도 스케줄러 없이 다음 claim 시점에 만료 임대를 재대기시킨다(지연 정리).
        expired_runs = SourceDiscoveryRun.objects.select_for_update().filter(
            status=SourceDiscoveryRun.Status.CLAIMED,
            lease_expires_at__lt=timezone.now(),
        )
        for expired_run in expired_runs:
            if expired_run.lease_count >= MAX_LEASES:
                expired_run.status = SourceDiscoveryRun.Status.EXPIRED
                expired_run.finished_at = timezone.now()
                expired_run.lease_token = ""
                expired_run.save(update_fields=["status", "finished_at", "lease_token"])
            else:
                expired_run.status = SourceDiscoveryRun.Status.PENDING
                expired_run.lease_token = ""
                expired_run.save(update_fields=["status", "lease_token"])

        run = (
            SourceDiscoveryRun.objects.select_for_update()
            .filter(status=SourceDiscoveryRun.Status.PENDING)
            .order_by("created_at")
            .first()
        )
        if run is None:
            return None

        run.status = SourceDiscoveryRun.Status.CLAIMED
        run.provider = provider
        run.lease_token = uuid.uuid4().hex
        run.lease_expires_at = timezone.now() + timedelta(seconds=LEASE_SECONDS)
        run.lease_count += 1
        if run.started_at is None:
            run.started_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "provider",
                "lease_token",
                "lease_expires_at",
                "lease_count",
                "started_at",
            ]
        )
        return run


def locked_run_with_valid_lease(*, run_id, lease_token):
    run = SourceDiscoveryRun.objects.select_for_update().get(pk=run_id)
    if run.status != SourceDiscoveryRun.Status.CLAIMED:
        raise LeaseInvalidError
    if not constant_time_compare(run.lease_token, lease_token):
        raise LeaseInvalidError
    if run.lease_expires_at is None or run.lease_expires_at <= timezone.now():
        raise LeaseInvalidError
    return run


def complete_run(*, run_id, lease_token, runner_status, failure_kind=""):
    with transaction.atomic():
        run = locked_run_with_valid_lease(run_id=run_id, lease_token=lease_token)

        if runner_status == "failed":
            error_summary = "러너가 실행 실패를 보고했다"
            # 허용 목록 밖 값은 무시한다 — 러너가 보낸 원문을 그대로 보간하지 않는다.
            if failure_kind in _ALLOWED_FAILURE_KINDS:
                error_summary = f"{error_summary} ({failure_kind})"
            run.status = SourceDiscoveryRun.Status.FAILED
            run.error_summary = error_summary
        else:
            candidate_statuses = list(run.candidates.values_list("status", flat=True))
            if not candidate_statuses or all(
                status == SourceCandidate.Status.PROMOTED for status in candidate_statuses
            ):
                run.status = SourceDiscoveryRun.Status.SUCCEEDED
            elif all(
                status == SourceCandidate.Status.FAILED for status in candidate_statuses
            ):
                run.status = SourceDiscoveryRun.Status.FAILED
            else:
                run.status = SourceDiscoveryRun.Status.PARTIALLY_FAILED

        run.finished_at = timezone.now()
        run.lease_token = ""
        run.save(update_fields=["status", "error_summary", "finished_at", "lease_token"])
        return run
