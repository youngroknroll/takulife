"""탐색 실행(run)·러너 heartbeat·임대 수명주기를 소유하는 서비스 계층."""
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from drafts.models import DiscoveryRunnerStatus, SourceDiscoveryRun

# 러너 폴링 주기에 여유를 둔 신선도 기준(초).
HEARTBEAT_FRESH_SECONDS = 120

# 에이전트 웹 탐색이 몇 분 걸릴 수 있어 여유를 둔 임대 시간(초).
LEASE_SECONDS = 900

# 최초 1회 + 재시도 1회까지만 재임대(정본 재시도 상한 결정).
MAX_LEASES = 2


class RunnerOfflineError(Exception):
    pass


class DiscoveryRunActiveError(Exception):
    pass


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
