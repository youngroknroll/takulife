"""drafts.discovery_runs 서비스 테스트."""
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from drafts.discovery_runs import (
    LEASE_SECONDS,
    DiscoveryRunActiveError,
    LeaseInvalidError,
    RunnerOfflineError,
    claim,
    complete_run,
    create_run,
    record_heartbeat,
)
from drafts.models import DiscoveryRunnerStatus, SourceCandidate, SourceDiscoveryRun


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
    assert claimed.lease_expires_at > timezone.now() + timedelta(seconds=LEASE_SECONDS - 10)
    assert claimed.lease_expires_at < timezone.now() + timedelta(seconds=LEASE_SECONDS + 10)


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


def test_실행_생성은_heartbeat_행_잠금_아래에서_검사와_생성을_수행한다(make_user):
    record_heartbeat(provider="claude-code")
    user = make_user()

    with CaptureQueriesContext(connection) as ctx:
        create_run(requested_by=user)

    # 단일 행 잠금이 활성 검사~생성을 직렬화한다는 계약(C5·F9와 같은 방식).
    assert any(
        "discoveryrunnerstatus" in query["sql"].lower() and "FOR UPDATE" in query["sql"].upper()
        for query in ctx.captured_queries
    )


def _make_claimed_run():
    return SourceDiscoveryRun.objects.create(
        status=SourceDiscoveryRun.Status.CLAIMED,
        lease_token="tok",
        lease_expires_at=timezone.now() + timedelta(seconds=900),
        lease_count=1,
    )


def _make_candidate(run, *, status, url):
    return SourceCandidate.objects.create(
        run=run,
        name="후보",
        url=url,
        source_type="html",
        sample_url=f"{url}/sample",
        status=status,
    )


def _setup_전_승격(run):
    _make_candidate(run, status=SourceCandidate.Status.PROMOTED, url="https://example.com/n1")
    _make_candidate(run, status=SourceCandidate.Status.PROMOTED, url="https://example.com/n2")
    return {"runner_status": "succeeded"}


def _setup_혼합(run):
    _make_candidate(run, status=SourceCandidate.Status.PROMOTED, url="https://example.com/n1")
    _make_candidate(run, status=SourceCandidate.Status.FAILED, url="https://example.com/n2")
    return {"runner_status": "succeeded"}


def _setup_전_실패(run):
    _make_candidate(run, status=SourceCandidate.Status.FAILED, url="https://example.com/n1")
    _make_candidate(run, status=SourceCandidate.Status.FAILED, url="https://example.com/n2")
    return {"runner_status": "succeeded"}


def _setup_후보_없음_성공(run):
    return {"runner_status": "succeeded"}


def _setup_러너_실패_보고(run):
    return {"runner_status": "failed", "failure_kind": "agent_timeout"}


@pytest.mark.parametrize(
    "setup, expected_status",
    [
        (_setup_전_승격, SourceDiscoveryRun.Status.SUCCEEDED),
        (_setup_혼합, SourceDiscoveryRun.Status.PARTIALLY_FAILED),
        (_setup_전_실패, SourceDiscoveryRun.Status.FAILED),
        (_setup_후보_없음_성공, SourceDiscoveryRun.Status.SUCCEEDED),
    ],
    ids=["전_승격", "혼합", "전_실패", "후보_없음_성공"],
)
def test_run_complete는_후보_상태_조합에_따라_최종_상태를_산출한다(setup, expected_status):
    run = _make_claimed_run()
    kwargs = setup(run)

    result = complete_run(run_id=run.pk, lease_token="tok", **kwargs)

    assert result.status == expected_status
    assert result.finished_at is not None
    if kwargs.get("runner_status") == "failed":
        assert result.error_summary
        assert result.error_summary == "러너가 실행 실패를 보고했다 (agent_timeout)"


# ---------------------------------------------------------------------------
# K1 — 러너 실패 보고 → FAILED (승격 후보 없음). 위 파라미터 목록에서 분리한
# 기존 계약(문구·단언 완전 동일 이식, 약화 없음) — S2가 "승격 후보가 있으면
# PARTIALLY_FAILED"를 추가해도 이 보호 행위는 그대로 지켜져야 한다.
# ---------------------------------------------------------------------------


def test_러너가_실패를_보고하고_승격된_후보가_없으면_run_상태는_FAILED로_유지된다():
    run = _make_claimed_run()
    kwargs = _setup_러너_실패_보고(run)

    result = complete_run(run_id=run.pk, lease_token="tok", **kwargs)

    assert result.status == SourceDiscoveryRun.Status.FAILED
    assert result.finished_at is not None
    assert result.error_summary
    assert result.error_summary == "러너가 실행 실패를 보고했다 (agent_timeout)"


# ---------------------------------------------------------------------------
# S2-1 — 러너가 failed를 보고해도 그 실행에서 PROMOTED 후보가 있으면
# 상태를 PARTIALLY_FAILED로 산출한다(오염 출력 사실은 error_summary로 유지).
# ---------------------------------------------------------------------------


def test_러너가_실패를_보고해도_승격된_후보가_있으면_run_상태는_PARTIALLY_FAILED로_산출된다():
    run = _make_claimed_run()
    _make_candidate(run, status=SourceCandidate.Status.PROMOTED, url="https://example.com/n1")
    _make_candidate(run, status=SourceCandidate.Status.FAILED, url="https://example.com/n2")

    result = complete_run(
        run_id=run.pk, lease_token="tok", runner_status="failed", failure_kind="agent_error"
    )

    assert result.status == SourceDiscoveryRun.Status.PARTIALLY_FAILED
    assert result.finished_at is not None
    assert result.error_summary == "러너가 실행 실패를 보고했다 (agent_error)"


def test_잘못된_lease로는_complete가_거부된다():
    run = _make_claimed_run()

    with pytest.raises(LeaseInvalidError):
        complete_run(run_id=run.pk, lease_token="wrong", runner_status="succeeded")

    run.refresh_from_db()
    assert run.status == SourceDiscoveryRun.Status.CLAIMED
    assert run.finished_at is None
