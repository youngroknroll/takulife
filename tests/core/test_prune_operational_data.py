"""core.management.commands.prune_operational_data 검증
(트랙 37 운영 데이터 보존 정리, prompt_plan.md 트랙 37 S1 참고).
"""
from datetime import timedelta
from io import StringIO

from axes.models import AccessAttempt, AccessFailureLog, AccessLog
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

import pytest

from core.models import AnalyticsEvent, ErrorGroup
from core.retention import prune_operational_data
from drafts.models import EventDraft, SourceDiscoveryRun
from staff.models import StaffActionLog

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_만료된_세션은_삭제되고_미만료_세션은_남는다():
    # RT-01
    now = timezone.now()
    Session.objects.create(
        session_key="expired-session-key",
        session_data="",
        expire_date=now - timedelta(days=1),
    )
    Session.objects.create(
        session_key="active-session-key",
        session_data="",
        expire_date=now + timedelta(days=1),
    )

    call_command("prune_operational_data", stdout=StringIO())

    assert not Session.objects.filter(session_key="expired-session-key").exists()
    assert Session.objects.filter(session_key="active-session-key").exists()


@pytest.mark.django_db
def test_91일_지난_AccessLog는_삭제되고_89일_지난_AccessLog는_남는다():
    # RT-02
    now = timezone.now()
    old = AccessLog.objects.create(username="stale-log")
    recent = AccessLog.objects.create(username="fresh-log")
    AccessLog.objects.filter(pk=old.pk).update(attempt_time=now - timedelta(days=91))
    AccessLog.objects.filter(pk=recent.pk).update(attempt_time=now - timedelta(days=89))

    call_command("prune_operational_data", stdout=StringIO())

    assert not AccessLog.objects.filter(username="stale-log").exists()
    assert AccessLog.objects.filter(username="fresh-log").exists()


@pytest.mark.django_db
def test_91일_지난_AccessFailureLog는_삭제되고_89일_지난_AccessFailureLog는_남는다():
    # RT-03
    now = timezone.now()
    old = AccessFailureLog.objects.create(username="stale-failure")
    recent = AccessFailureLog.objects.create(username="fresh-failure")
    AccessFailureLog.objects.filter(pk=old.pk).update(attempt_time=now - timedelta(days=91))
    AccessFailureLog.objects.filter(pk=recent.pk).update(attempt_time=now - timedelta(days=89))

    call_command("prune_operational_data", stdout=StringIO())

    assert not AccessFailureLog.objects.filter(username="stale-failure").exists()
    assert AccessFailureLog.objects.filter(username="fresh-failure").exists()


@pytest.mark.django_db
def test_오래된_AccessAttempt는_보존_정리로_지워지지_않는다():
    # RT-04
    now = timezone.now()
    attempt = AccessAttempt.objects.create(username="ancient-attempt", failures_since_start=0)
    AccessAttempt.objects.filter(pk=attempt.pk).update(attempt_time=now - timedelta(days=200))

    call_command("prune_operational_data", stdout=StringIO())

    assert AccessAttempt.objects.filter(username="ancient-attempt").exists()


@pytest.mark.django_db
def test_91일_지난_ErrorGroup은_삭제되고_89일_지난_ErrorGroup은_남는다():
    # RT-05
    now = timezone.now()
    ErrorGroup.objects.create(
        source=ErrorGroup.Source.BACKEND,
        fingerprint="a" * 64,
        error_type="StaleError",
        location="stale-location",
        last_seen=now - timedelta(days=91),
    )
    ErrorGroup.objects.create(
        source=ErrorGroup.Source.BACKEND,
        fingerprint="b" * 64,
        error_type="FreshError",
        location="fresh-location",
        last_seen=now - timedelta(days=89),
    )

    call_command("prune_operational_data", stdout=StringIO())

    assert not ErrorGroup.objects.filter(fingerprint="a" * 64).exists()
    assert ErrorGroup.objects.filter(fingerprint="b" * 64).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "create_row",
    [
        lambda: AnalyticsEvent.objects.create(
            event_name=AnalyticsEvent.EventName.EVENT_LIST_VIEWED
        ),
        lambda: StaffActionLog.objects.create(action=StaffActionLog.Action.APPROVE),
        lambda: EventDraft.objects.create(source_url="https://example.com/rt-06-event-draft"),
        lambda: SourceDiscoveryRun.objects.create(),
    ],
    ids=["AnalyticsEvent", "StaffActionLog", "EventDraft", "SourceDiscoveryRun"],
)
def test_분석_이벤트_스태프_로그_드래프트_탐색실행은_90일_넘어도_보존_정리로_지워지지_않는다(create_row):
    # RT-06
    row = create_row()
    type(row).objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(days=200))

    prune_operational_data()

    assert type(row).objects.filter(pk=row.pk).exists()


@pytest.mark.django_db
def test_dry_run은_아무것도_지우지_않고_대상별_건수만_보고한다():
    # RT-07
    now = timezone.now()
    Session.objects.create(
        session_key="rt07-session", session_data="", expire_date=now - timedelta(days=1)
    )
    Session.objects.create(
        session_key="rt07-active-session", session_data="", expire_date=now + timedelta(days=1)
    )
    access_log = AccessLog.objects.create(username="rt07-access-log")
    AccessLog.objects.filter(pk=access_log.pk).update(attempt_time=now - timedelta(days=91))
    ErrorGroup.objects.create(
        source=ErrorGroup.Source.BACKEND,
        fingerprint="c" * 64,
        error_type="Rt07Error",
        location="rt07-location",
        last_seen=now - timedelta(days=91),
    )

    result = prune_operational_data(dry_run=True)

    assert Session.objects.filter(session_key="rt07-session").exists()
    assert AccessLog.objects.filter(username="rt07-access-log").exists()
    assert ErrorGroup.objects.filter(fingerprint="c" * 64).exists()
    assert result["sessions"]["count"] == 1
    assert result["access_logs"]["count"] == 1
    assert result["error_groups"]["count"] == 1
    assert result["access_failure_logs"]["count"] == 0


@pytest.mark.django_db
def test_dry_run은_AccessFailureLog_건수도_보고한다():
    # RT-07
    now = timezone.now()
    access_failure_log = AccessFailureLog.objects.create(username="rt07-access-failure-log")
    AccessFailureLog.objects.filter(pk=access_failure_log.pk).update(
        attempt_time=now - timedelta(days=91)
    )

    result = prune_operational_data(dry_run=True)

    assert AccessFailureLog.objects.filter(username="rt07-access-failure-log").exists()
    assert result["access_failure_logs"]["count"] == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_한_대상_삭제가_실패해도_다른_대상은_지워지고_CommandError가_난다(monkeypatch):
    # RT-08
    now = timezone.now()
    Session.objects.create(
        session_key="rt08-session", session_data="", expire_date=now - timedelta(days=1)
    )
    access_log = AccessLog.objects.create(username="rt08-access-log")
    AccessLog.objects.filter(pk=access_log.pk).update(attempt_time=now - timedelta(days=91))

    def flaky_clearsessions(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("core.retention.call_command", flaky_clearsessions)

    out = StringIO()
    with pytest.raises(CommandError):
        call_command("prune_operational_data", stdout=out)

    assert not AccessLog.objects.filter(username="rt08-access-log").exists()
    assert "error=RuntimeError" in out.getvalue()  # RT-20


@pytest.mark.django_db
def test_명령_실행_결과가_대상별_라벨과_건수로_표준출력에_남는다():
    # RT-09
    now = timezone.now()
    Session.objects.create(
        session_key="rt09-session", session_data="", expire_date=now - timedelta(days=1)
    )
    access_log = AccessLog.objects.create(username="rt09-access-log")
    AccessLog.objects.filter(pk=access_log.pk).update(attempt_time=now - timedelta(days=91))
    access_failure_log = AccessFailureLog.objects.create(username="rt09-access-failure-log")
    AccessFailureLog.objects.filter(pk=access_failure_log.pk).update(
        attempt_time=now - timedelta(days=91)
    )
    ErrorGroup.objects.create(
        source=ErrorGroup.Source.BACKEND,
        fingerprint="d" * 64,
        error_type="Rt09Error",
        location="rt09-location",
        last_seen=now - timedelta(days=91),
    )

    out = StringIO()
    call_command("prune_operational_data", stdout=out)
    output = out.getvalue()

    for label in ("sessions", "access_logs", "access_failure_logs", "error_groups"):
        assert label in output
    assert "1" in output


@pytest.mark.django_db
def test_days가_1_미만이면_함수가_ValueError를_낸다():
    # RT-17
    with pytest.raises(ValueError):
        prune_operational_data(days=0)


@pytest.mark.django_db
@pytest.mark.parametrize("days", [0, -1])
def test_days가_1_미만이면_명령은_아무것도_지우지_않고_CommandError를_낸다(days):
    # RT-17
    now = timezone.now()
    AccessLog.objects.create(username="rt17-access-log")
    AccessLog.objects.filter(username="rt17-access-log").update(
        attempt_time=now - timedelta(days=91)
    )
    ErrorGroup.objects.create(
        source=ErrorGroup.Source.BACKEND,
        fingerprint="e" * 64,
        error_type="Rt17Error",
        location="rt17-location",
        last_seen=now - timedelta(days=91),
    )
    Session.objects.create(
        session_key="rt17-session", session_data="", expire_date=now + timedelta(days=1)
    )

    with pytest.raises(CommandError):
        call_command("prune_operational_data", "--days", str(days), stdout=StringIO())

    assert AccessLog.objects.filter(username="rt17-access-log").exists()
    assert ErrorGroup.objects.filter(fingerprint="e" * 64).exists()
    assert Session.objects.filter(session_key="rt17-session").exists()


@pytest.mark.django_db
def test_dry_run_옵션이_전달되면_아무것도_지우지_않고_dry_run으로_시작한다():
    # RT-18
    now = timezone.now()
    access_log = AccessLog.objects.create(username="rt18-access-log")
    AccessLog.objects.filter(pk=access_log.pk).update(attempt_time=now - timedelta(days=91))

    out = StringIO()
    call_command("prune_operational_data", "--dry-run", stdout=out)
    output = out.getvalue()

    assert output.splitlines()[0] == "dry-run"
    assert AccessLog.objects.filter(username="rt18-access-log").exists()


@pytest.mark.django_db
def test_days_옵션이_전달되면_그_기준으로_삭제한다():
    # RT-18
    now = timezone.now()
    old = AccessLog.objects.create(username="rt18-old-access-log")
    recent = AccessLog.objects.create(username="rt18-recent-access-log")
    AccessLog.objects.filter(pk=old.pk).update(attempt_time=now - timedelta(days=31))
    AccessLog.objects.filter(pk=recent.pk).update(attempt_time=now - timedelta(days=29))

    call_command("prune_operational_data", "--days", "30", stdout=StringIO())

    assert not AccessLog.objects.filter(username="rt18-old-access-log").exists()
    assert AccessLog.objects.filter(username="rt18-recent-access-log").exists()
