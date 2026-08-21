"""러너 API 인증 계약 테스트 — X-Runner-Token 헤더와 DRAFT_DISCOVERY_RUNNER_TOKEN."""
from datetime import timedelta

import pytest
from django.utils import timezone

from drafts.models import DiscoveryRunnerStatus, DraftSource, SourceCandidate, SourceDiscoveryRun


pytestmark = [pytest.mark.django_db, pytest.mark.web]

HEARTBEAT_URL = "/api/discovery/runner/heartbeat/"
CLAIM_URL = "/api/discovery/runner/claim/"
CANDIDATES_URL = "/api/discovery/runner/runs/1/candidates/"
COMPLETE_URL = "/api/discovery/runner/runs/1/complete/"

_RUNNER_TOKEN = "runner-secret"


@pytest.fixture
def runner_headers(settings):
    """유효 러너 토큰을 설정하고 헤더 kwargs를 돌려준다(테스트 전반 재사용)."""
    settings.DRAFT_DISCOVERY_RUNNER_TOKEN = _RUNNER_TOKEN
    return {"HTTP_X_RUNNER_TOKEN": _RUNNER_TOKEN}


def _candidates_url(run_id):
    return f"/api/discovery/runner/runs/{run_id}/candidates/"


def _complete_url(run_id):
    return f"/api/discovery/runner/runs/{run_id}/complete/"

_ENDPOINTS = [HEARTBEAT_URL, CLAIM_URL, CANDIDATES_URL, COMPLETE_URL]
_ENDPOINT_IDS = ["하트비트", "클레임", "후보제출", "완료"]


@pytest.mark.parametrize("url", _ENDPOINTS, ids=_ENDPOINT_IDS)
@pytest.mark.parametrize(
    "header_kwargs",
    [{}, {"HTTP_X_RUNNER_TOKEN": "some-arbitrary-value"}],
    ids=["헤더_없음", "임의_헤더"],
)
def test_러너_토큰이_설정되지_않으면_모든_러너_엔드포인트가_403을_반환한다(
    client, settings, url, header_kwargs
):
    settings.DRAFT_DISCOVERY_RUNNER_TOKEN = ""

    # constant_time_compare("", "") == True인 함정을 막기 위해 빈 설정에서는
    # 비교 전에 명시적으로 거부해야 한다 — 빈 헤더로도 뚫리면 안 된다.
    response = client.post(url, data={}, content_type="application/json", **header_kwargs)

    assert response.status_code == 403


def test_잘못된_토큰은_403_올바른_토큰은_통과한다(client, settings):
    settings.DRAFT_DISCOVERY_RUNNER_TOKEN = "runner-secret"

    wrong_response = client.post(
        HEARTBEAT_URL,
        data={"provider": "claude-code"},
        content_type="application/json",
        HTTP_X_RUNNER_TOKEN="wrong-token",
    )

    assert wrong_response.status_code == 403

    correct_response = client.post(
        HEARTBEAT_URL,
        data={"provider": "claude-code"},
        content_type="application/json",
        HTTP_X_RUNNER_TOKEN="runner-secret",
    )

    assert 200 <= correct_response.status_code < 300
    assert DiscoveryRunnerStatus.objects.count() == 1


def test_claim_응답은_임대_정보와_기존_소스와_제외_호스트를_포함한다(client, runner_headers):
    SourceDiscoveryRun.objects.create(status=SourceDiscoveryRun.Status.PENDING)
    DraftSource.objects.create(
        name="기존", url="https://old.example.com/feed", source_type="rss"
    )

    response = client.post(
        CLAIM_URL,
        data={"provider": "claude-code"},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["run_id"]
    assert run["lease_token"]
    assert run["lease_expires_at"]
    assert run["max_candidates"] == 10
    assert "https://old.example.com/feed" in run["existing_source_urls"]
    assert "x.com" in run["excluded_hostnames"]
    assert "instagram.com" in run["excluded_hostnames"]


def test_claim은_대기_실행이_없으면_run_None을_반환한다(client, runner_headers):
    response = client.post(
        CLAIM_URL,
        data={"provider": "claude-code"},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"run": None}


def _make_claimed_run():
    return SourceDiscoveryRun.objects.create(
        status=SourceDiscoveryRun.Status.CLAIMED,
        lease_token="tok",
        lease_expires_at=timezone.now() + timedelta(seconds=900),
        lease_count=1,
    )


def test_후보_제출은_유효_페이로드에_201_형태_위반에_400을_반환한다(client, runner_headers):
    run = _make_claimed_run()

    # 스키마 위반(name 누락) payload는 네트워크를 타지 않고 즉시 실패 저장된다 —
    # 이 엔드포인트 계약(201 + FAILED/SCHEMA)만 확인하면 되므로 네트워크 검증
    # 단계를 패치할 필요가 없다.
    schema_invalid_payload = {
        "url": "https://example.com/notice",
        "source_type": "html",
        "sample_url": "https://example.com/notice/1",
    }

    valid_response = client.post(
        _candidates_url(run.pk),
        data={"lease_token": "tok", "candidate": schema_invalid_payload},
        content_type="application/json",
        **runner_headers,
    )

    assert valid_response.status_code == 201
    body = valid_response.json()
    assert body["status"] == "failed"
    assert body["failure_stage"] == "schema"

    malformed_response = client.post(
        _candidates_url(run.pk),
        data={"candidate": "문자열"},
        content_type="application/json",
        **runner_headers,
    )

    assert malformed_response.status_code == 400

    missing_lease_response = client.post(
        _candidates_url(run.pk),
        data={"candidate": schema_invalid_payload},
        content_type="application/json",
        **runner_headers,
    )

    assert missing_lease_response.status_code == 400

    wrong_lease_response = client.post(
        _candidates_url(run.pk),
        data={"lease_token": "wrong", "candidate": schema_invalid_payload},
        content_type="application/json",
        **runner_headers,
    )

    assert wrong_lease_response.status_code == 409


def test_complete는_실행_상태를_저장하고_잘못된_값은_거부한다(client, runner_headers):
    run = _make_claimed_run()
    SourceCandidate.objects.create(
        run=run,
        name="후보",
        url="https://example.com/n1",
        source_type="html",
        sample_url="https://example.com/n1/sample",
        status=SourceCandidate.Status.PROMOTED,
    )

    response = client.post(
        _complete_url(run.pk),
        data={"lease_token": "tok", "runner_status": "succeeded"},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    run.refresh_from_db()
    assert run.status == SourceDiscoveryRun.Status.SUCCEEDED

    invalid_status_response = client.post(
        _complete_url(run.pk),
        data={"lease_token": "tok", "runner_status": "weird"},
        content_type="application/json",
        **runner_headers,
    )

    assert invalid_status_response.status_code == 400

    not_found_response = client.post(
        _complete_url(999999),
        data={"lease_token": "tok", "runner_status": "succeeded"},
        content_type="application/json",
        **runner_headers,
    )

    assert not_found_response.status_code == 404


def test_discovery_runner_스로틀_scope가_등록되어_있다(settings):
    rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["discovery_runner"]

    assert rate.endswith("/minute")
