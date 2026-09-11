"""러너 이벤트 제출 엔드포인트 계약 테스트 — 생성·중복·스키마 위반·상한
초과·불안전 URL을 각각 다른 상태코드로 옮기는지 본다."""
from datetime import timedelta

import pytest
from django.utils import timezone

from drafts.models import EventDraft, SourceDiscoveryRun
from drafts.robots import RobotsCheckResult
from drafts.url_safety import UnsafeFetchUrlError


pytestmark = [pytest.mark.django_db, pytest.mark.web]

_RUNNER_TOKEN = "runner-secret"


@pytest.fixture
def runner_headers(settings):
    settings.DRAFT_DISCOVERY_RUNNER_TOKEN = _RUNNER_TOKEN
    return {"HTTP_X_RUNNER_TOKEN": _RUNNER_TOKEN}


def _drafts_url(run_id):
    return f"/api/discovery/runner/runs/{run_id}/drafts/"


def _make_claimed_run():
    return SourceDiscoveryRun.objects.create(
        status=SourceDiscoveryRun.Status.CLAIMED,
        lease_token="tok",
        lease_expires_at=timezone.now() + timedelta(seconds=900),
        lease_count=1,
    )


class _AllowAllRobots:
    def check(self, url):
        return RobotsCheckResult(True, None)


def _neutralize_server_recheck(monkeypatch):
    # 네트워크가 관심사가 아닌 케이스는 서버 재확인(KW-07)을 타지 않는다.
    monkeypatch.setattr(
        "drafts.agent_drafts.validate_fetch_url", lambda url, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("drafts.agent_drafts.RobotsChecker", _AllowAllRobots)
    monkeypatch.setattr(
        "drafts.agent_drafts.fetch_html", lambda url, **kwargs: "<html></html>"
    )


def _valid_event_payload(source_url):
    return {
        "source_url": source_url,
        "raw_title": "무제 팝업 안내",
        "raw_text": "원문 캡션...",
        "platform": "web",
        "judgment": "official",
        "official_basis": "공식 홈페이지 명시",
        "source_name": "공식 홈페이지",
        "fields": {
            "title": "하츠네 미쿠 팝업스토어",
            "work_title": "하츠네 미쿠",
            "category": "popup_store",
            "region": "seoul",
            "location_name": "용산 아이파크몰",
            "start_date": "2026-09-01",
            "end_date": "2026-09-22",
            "summary": "요약",
        },
        "confidence": 0.9,
        "note": "",
    }


def _post_event(client, runner_headers, run, event):
    return client.post(
        _drafts_url(run.pk),
        data={"lease_token": "tok", "event": event},
        content_type="application/json",
        **runner_headers,
    )


def _case_생성(client, runner_headers, monkeypatch):
    _neutralize_server_recheck(monkeypatch)
    run = _make_claimed_run()
    event = _valid_event_payload("https://official-site.example.com/event")

    response = _post_event(client, runner_headers, run, event)

    body = response.json()
    assert isinstance(body.get("draft_id"), int)
    return response, 201, {"status": "created"}


def _case_중복(client, runner_headers, monkeypatch):
    _neutralize_server_recheck(monkeypatch)
    run = _make_claimed_run()
    event = _valid_event_payload("https://official-site.example.com/event")

    first_response = _post_event(client, runner_headers, run, event)
    first_draft_id = first_response.json()["draft_id"]

    second_response = _post_event(client, runner_headers, run, event)

    return second_response, 200, {"status": "duplicate", "draft_id": first_draft_id}


def _case_스키마_위반(client, runner_headers, monkeypatch):
    run = _make_claimed_run()
    event = _valid_event_payload("https://official-site.example.com/event")
    del event["fields"]

    response = _post_event(client, runner_headers, run, event)

    return response, 400, None


def _case_상한_초과(client, runner_headers, monkeypatch):
    from drafts.agent_drafts import MAX_EVENTS_PER_RUN

    _neutralize_server_recheck(monkeypatch)
    run = _make_claimed_run()
    EventDraft.objects.bulk_create(
        [
            EventDraft(
                source_url=f"https://existing.example.com/event-{i}",
                discovery_run=run,
            )
            for i in range(MAX_EVENTS_PER_RUN)
        ]
    )
    event = _valid_event_payload("https://official-site.example.com/new-event")

    response = _post_event(client, runner_headers, run, event)

    return response, 400, None


def _case_불안전_URL(client, runner_headers, monkeypatch):
    def raise_unsafe(url, **kwargs):
        raise UnsafeFetchUrlError

    monkeypatch.setattr("drafts.agent_drafts.validate_fetch_url", raise_unsafe)
    run = _make_claimed_run()
    event = _valid_event_payload("https://official-site.example.com/event")

    response = _post_event(client, runner_headers, run, event)

    return response, 400, None


@pytest.mark.parametrize(
    "case",
    [_case_생성, _case_중복, _case_스키마_위반, _case_상한_초과, _case_불안전_URL],
    ids=["생성", "중복", "스키마_위반", "상한_초과", "불안전_URL"],
)
def test_이벤트_제출은_생성_중복_스키마_위반_상한_초과_불안전_URL을_각각_다른_상태코드로_옮긴다(
    case, client, runner_headers, monkeypatch
):
    response, expected_status, expected_body = case(client, runner_headers, monkeypatch)

    assert response.status_code == expected_status
    if expected_body is not None:
        body = response.json()
        for key, value in expected_body.items():
            assert body[key] == value
