"""staff.views — POST /staff/draft-discovery/run/ (prompt_plan.md "콘솔 수집
실행 버튼").

Synchronously calls the existing discover_drafts management command
(stdout captured via StringIO) and surfaces its outcome as a Django message,
PRG-redirecting back to the dashboard. The view itself only decides: flag-off
short-circuit (no command execution, no audit log — see module docstring in
discover_drafts.py, "being off is an intended state") vs. an actual run
(success / CommandError partial-failure / unclassified exception), each of
which is audit-logged.

`call_command` is monkeypatched at this module's import location
(staff.views.call_command) for the run-outcome tests below — discover_drafts'
own internal behaviour (robots, dedup, fetch, etc.) is already covered by
tests/test_discover_drafts_command.py and is out of scope here.
"""
import pytest
from django.core.management import CommandError

from staff.models import StaffActionLog


RUN_URL = "/staff/draft-discovery/run/"


@pytest.mark.django_db
def test_run_anonymous_redirects_to_login(client):
    resp = client.post(RUN_URL)

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next={RUN_URL}"


@pytest.mark.django_db
def test_run_non_staff_returns_403(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.post(RUN_URL)

    assert resp.status_code == 403


@pytest.mark.django_db
def test_run_get_redirects_to_dashboard_instead_of_405(staff_client):
    """PR-D1 item 2: a GET (e.g. a session-expired POST bounced through
    login's `next=` redirect) must not dead-end on a 405 — it redirects back
    to the dashboard instead, same as the flag-off short-circuit."""
    staff, client = staff_client()

    resp = client.get(RUN_URL)

    assert resp.status_code == 302
    assert resp.url == "/staff/dashboard/"


@pytest.mark.django_db
def test_run_flag_off_shows_info_message_and_does_not_execute_command(staff_client, settings, monkeypatch, fail_if_called):
    settings.DRAFT_DISCOVERY_ENABLED = False
    staff, client = staff_client()

    monkeypatch.setattr("staff.views.call_command", fail_if_called)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("DRAFT_DISCOVERY_ENABLED=False" in m for m in messages)
    assert not StaffActionLog.objects.filter(action=StaffActionLog.Action.DRAFT_DISCOVER).exists()


@pytest.mark.django_db
def test_run_no_enabled_sources_shows_info_message_and_does_not_execute_command(staff_client, settings, monkeypatch, make_source, fail_if_called):
    """PR-D1 item 6: flag on, but zero enabled DraftSource rows — the same
    "no-op is an intended state" treatment as the flag-off case: an info
    message, no command execution, no audit log entry."""
    settings.DRAFT_DISCOVERY_ENABLED = True
    staff, client = staff_client()
    make_source(name="disabled-source", url="https://example.com/disabled-feed/", enabled=False)

    monkeypatch.setattr("staff.views.call_command", fail_if_called)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("활성 수집 소스가 없습니다" in m for m in messages)
    assert not StaffActionLog.objects.filter(action=StaffActionLog.Action.DRAFT_DISCOVER).exists()


@pytest.mark.django_db
def test_run_success_shows_summary_message_and_writes_audit_log(staff_client, settings, monkeypatch, make_source):
    settings.DRAFT_DISCOVERY_ENABLED = True
    staff, client = staff_client()
    make_source(name="enabled-source", url="https://example.com/enabled-feed/")

    def _fake_call_command(name, *args, stdout=None, **kwargs):
        assert name == "discover_drafts"
        stdout.write("발견 0건 (상한 도달로 0건 보류) / 생성 0건\n")
        stdout.write("스킵 - 중복 0건, robots 불허 0건, robots 페치 실패 0건, 빈 콘텐츠 0건\n")
        stdout.write("에러 0건\n")

    monkeypatch.setattr("staff.views.call_command", _fake_call_command)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("생성 0건" in m for m in messages)
    log = StaffActionLog.objects.get(action=StaffActionLog.Action.DRAFT_DISCOVER)
    assert log.actor_id == staff.id


@pytest.mark.django_db
def test_run_partial_failure_shows_error_message_and_writes_audit_log(staff_client, settings, monkeypatch, make_source):
    settings.DRAFT_DISCOVERY_ENABLED = True
    staff, client = staff_client()
    make_source(name="enabled-source", url="https://example.com/enabled-feed/")

    def _fake_call_command(name, *args, stdout=None, **kwargs):
        stdout.write("발견 1건 (상한 도달로 0건 보류) / 생성 0건\n")
        raise CommandError("discover_drafts: 1건 에러 발생 — 위 로그 참고")

    monkeypatch.setattr("staff.views.call_command", _fake_call_command)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("에러" in m or "실패" in m for m in messages)
    log = StaffActionLog.objects.get(action=StaffActionLog.Action.DRAFT_DISCOVER)
    assert log.actor_id == staff.id


@pytest.mark.django_db
def test_run_unclassified_exception_shows_error_message_and_does_not_propagate(staff_client, settings, monkeypatch, make_source):
    settings.DRAFT_DISCOVERY_ENABLED = True
    staff, client = staff_client()
    make_source(name="enabled-source", url="https://example.com/enabled-feed/")

    def _fake_call_command(name, *args, stdout=None, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("staff.views.call_command", _fake_call_command)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("오류" in m for m in messages)
    log = StaffActionLog.objects.get(action=StaffActionLog.Action.DRAFT_DISCOVER)
    assert log.actor_id == staff.id
