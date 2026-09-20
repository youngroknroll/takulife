"""스태프 대시보드 실시간 수집 현황 조회 API 계약."""
import pytest

from drafts.discovery_runs import record_heartbeat
from drafts.models import EventDraft, SourceCandidate, SourceDiscoveryRun

pytestmark = pytest.mark.web

LIVE_URL = "/staff/api/discovery/live/"


@pytest.mark.django_db
@pytest.mark.parametrize("login_as_regular_user", [False, True], ids=["익명", "비스태프"])
def test_관리자가_아니면_수집_실시간_현황을_조회할_수_없다(client, make_user, login_as_regular_user):
    if login_as_regular_user:
        client.force_login(make_user())

    response = client.get(LIVE_URL)

    assert response.status_code == 403


@pytest.mark.django_db
def test_스태프는_수집_실시간_현황을_200으로_받는다(staff_client):
    _, client = staff_client()

    response = client.get(LIVE_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_실시간_현황_응답은_러너와_최근_실행_목록을_순수_JSON으로_담는다(staff_client):
    _, client = staff_client()
    record_heartbeat(provider="claude-code", phase="exploring", detail='검색어 "미쿠" 검색 중')
    run = SourceDiscoveryRun.objects.create(
        status=SourceDiscoveryRun.Status.SUCCEEDED,
        event_outcomes=[
            {"url": "https://example.com/e1", "outcome": "created", "reason": ""},
        ],
    )
    SourceCandidate.objects.create(
        run=run,
        name="후보",
        url="https://example.com/n1",
        source_type="html",
        sample_url="https://example.com/n1/sample",
        status=SourceCandidate.Status.PROMOTED,
    )
    EventDraft.objects.create(source_url="https://example.com/e1", discovery_run=run)

    response = client.get(LIVE_URL)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"runner", "runs", "server_time"}
    assert set(body["runner"].keys()) == {
        "online",
        "phase",
        "phase_label",
        "detail",
        "progress_visible",
        "current_run_id",
        "last_heartbeat_at",
        "active",
    }
    run_row = body["runs"][0]
    assert set(run_row.keys()) == {
        "id",
        "status",
        "status_label",
        "tone",
        "query",
        "created_at",
        "promoted_count",
        "failed_count",
        "events_created",
        "events_excluded",
        "events_failed",
        "error_summary",
        "outcomes",
    }
    outcome_row = run_row["outcomes"][0]
    assert set(outcome_row.keys()) == {
        "display_url",
        "outcome",
        "outcome_label",
        "tone",
        "reason_label",
    }
    assert "runs_html" not in body
    assert "runner_html" not in body


@pytest.mark.slow
@pytest.mark.django_db
def test_실시간_현황_조회는_분당_40회로_제한된다(staff_client, clear_cache):
    _, client = staff_client()

    for i in range(40):
        response = client.get(LIVE_URL)
        assert response.status_code == 200, f"request {i} should succeed"

    throttled = client.get(LIVE_URL)

    assert throttled.status_code == 429
