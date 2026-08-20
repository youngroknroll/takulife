"""drafts.discovery_runs 서비스 테스트."""
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from drafts.discovery_runs import (
    DiscoveryRunActiveError,
    RunnerOfflineError,
    claim,
    create_run,
    record_heartbeat,
)
from drafts.models import DiscoveryRunnerStatus, SourceDiscoveryRun


pytestmark = [pytest.mark.django_db, pytest.mark.domain]


def test_heartbeat를_두_번_기록해도_상태_행은_하나로_갱신된다():
    record_heartbeat(provider="claude-code")
    first_heartbeat_at = DiscoveryRunnerStatus.objects.get().last_heartbeat_at

    record_heartbeat(provider="claude-code")

    assert DiscoveryRunnerStatus.objects.count() == 1
    status = DiscoveryRunnerStatus.objects.get()
    assert status.provider == "claude-code"
    assert status.last_heartbeat_at >= first_heartbeat_at


def test_러너_heartbeat가_신선하면_탐색_실행이_pending으로_생성된다(make_user):
    record_heartbeat(provider="claude-code")
    user = make_user()

    run = create_run(requested_by=user)

    assert run.status == SourceDiscoveryRun.Status.PENDING
    assert run.requested_by == user
    assert run.lease_token == ""
    assert run.lease_count == 0


def test_heartbeat가_120초를_초과하면_실행_생성이_러너_오프라인_사유로_거부된다(make_user):
    record_heartbeat(provider="claude-code")
    DiscoveryRunnerStatus.objects.update(
        last_heartbeat_at=timezone.now() - timedelta(seconds=121)
    )
    user = make_user()

    with pytest.raises(RunnerOfflineError):
        create_run(requested_by=user)

    assert SourceDiscoveryRun.objects.count() == 0


def test_heartbeat_기록이_없으면_실행_생성이_러너_오프라인_사유로_거부된다(make_user):
    user = make_user()

    with pytest.raises(RunnerOfflineError):
        create_run(requested_by=user)

    assert SourceDiscoveryRun.objects.count() == 0


@pytest.mark.parametrize(
    "status",
    [SourceDiscoveryRun.Status.PENDING, SourceDiscoveryRun.Status.CLAIMED],
    ids=["대기중", "임대중"],
)
def test_대기중이거나_임대된_실행이_있으면_새_실행_생성이_거부된다(make_user, status):
    record_heartbeat(provider="claude-code")
    user = make_user()
    SourceDiscoveryRun.objects.create(requested_by=user, status=status)

    with pytest.raises(DiscoveryRunActiveError):
        create_run(requested_by=user)

    assert SourceDiscoveryRun.objects.count() == 1


def test_종결된_실행만_있으면_새_실행이_생성된다(make_user):
    record_heartbeat(provider="claude-code")
    user = make_user()
    SourceDiscoveryRun.objects.create(
        requested_by=user, status=SourceDiscoveryRun.Status.SUCCEEDED
    )

    run = create_run(requested_by=user)

    assert run.status == SourceDiscoveryRun.Status.PENDING
    assert SourceDiscoveryRun.objects.count() == 2


def test_claim은_가장_오래된_대기_실행을_임대하고_토큰과_만료시각을_채운다(make_user):
    user = make_user()
    older_run = SourceDiscoveryRun.objects.create(
        requested_by=user, status=SourceDiscoveryRun.Status.PENDING
    )
    SourceDiscoveryRun.objects.create(
        requested_by=user, status=SourceDiscoveryRun.Status.PENDING
    )

    claimed = claim(provider="claude-code")

    assert claimed.pk == older_run.pk
    assert claimed.status == SourceDiscoveryRun.Status.CLAIMED
    assert claimed.lease_token != ""
    assert claimed.lease_count == 1
    assert claimed.provider == "claude-code"
    assert claimed.started_at is not None
    assert claimed.lease_expires_at > timezone.now() + timedelta(seconds=890)
    assert claimed.lease_expires_at < timezone.now() + timedelta(seconds=910)


def test_대기_실행이_없으면_claim은_임대_없음을_반환한다():
    assert claim(provider="claude-code") is None


def test_임대가_만료된_실행은_claim_시점에_재대기되어_다시_임대된다(make_user):
    user = make_user()
    run = SourceDiscoveryRun.objects.create(
        requested_by=user,
        status=SourceDiscoveryRun.Status.CLAIMED,
        lease_token="oldtoken",
        lease_count=1,
        lease_expires_at=timezone.now() - timedelta(seconds=1),
    )

    claimed = claim(provider="claude-code")

    assert claimed.pk == run.pk
    assert claimed.status == SourceDiscoveryRun.Status.CLAIMED
    assert claimed.lease_token != "oldtoken"
    assert claimed.lease_count == 2


def test_임대_상한을_소진한_만료_실행은_expired로_닫힌다(make_user):
    user = make_user()
    run = SourceDiscoveryRun.objects.create(
        requested_by=user,
        status=SourceDiscoveryRun.Status.CLAIMED,
        lease_token="oldtoken",
        lease_count=2,
        lease_expires_at=timezone.now() - timedelta(seconds=1),
    )

    claimed = claim(provider="claude-code")

    assert claimed is None
    run.refresh_from_db()
    assert run.status == SourceDiscoveryRun.Status.EXPIRED
    assert run.finished_at is not None


def test_claim의_임대는_FOR_UPDATE_잠금_아래에서_일어난다(make_user):
    record_heartbeat(provider="claude-code")
    user = make_user()
    SourceDiscoveryRun.objects.create(
        requested_by=user, status=SourceDiscoveryRun.Status.PENDING
    )

    with CaptureQueriesContext(connection) as ctx:
        claim(provider="claude-code")

    assert any("FOR UPDATE" in query["sql"].upper() for query in ctx.captured_queries)
