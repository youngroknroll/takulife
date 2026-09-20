"""러너 API 인증 계약 테스트 — X-Runner-Token 헤더와 DRAFT_DISCOVERY_RUNNER_TOKEN."""
import logging
from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import Category
from core.vocab import CATEGORY, REGION
from drafts.discovery_runs import record_heartbeat, runner_is_online
from drafts.models import (
    DiscoveryRunnerStatus,
    DraftSource,
    EventDraft,
    SourceCandidate,
    SourceDiscoveryRun,
)
from drafts.queries import runner_status
from drafts.runner_views import RunnerTokenThrottle


pytestmark = [pytest.mark.django_db, pytest.mark.web]

HEARTBEAT_URL = "/api/discovery/runner/heartbeat/"
CLAIM_URL = "/api/discovery/runner/claim/"
CANDIDATES_URL = "/api/discovery/runner/runs/1/candidates/"
COMPLETE_URL = "/api/discovery/runner/runs/1/complete/"
DRAFTS_URL = "/api/discovery/runner/runs/1/drafts/"
KNOWN_URL = "/api/discovery/runner/drafts/known/"
OFFLINE_URL = "/api/discovery/runner/offline/"

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

_ENDPOINTS = [HEARTBEAT_URL, CLAIM_URL, CANDIDATES_URL, COMPLETE_URL, DRAFTS_URL, KNOWN_URL, OFFLINE_URL]
_ENDPOINT_IDS = ["하트비트", "클레임", "후보제출", "완료", "이벤트제출", "알려진URL필터", "오프라인"]


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


def test_유효한_토큰으로_오프라인을_보고하면_204와_함께_즉시_오프라인으로_기록된다(client, runner_headers):
    record_heartbeat(provider="claude-code")

    response = client.post(
        OFFLINE_URL, data={}, content_type="application/json", **runner_headers
    )

    assert response.status_code == 204
    assert runner_is_online(status_row=runner_status()) is False


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


def test_claim_응답은_카테고리와_지역_어휘_목록을_포함한다(client, runner_headers):
    SourceDiscoveryRun.objects.create(status=SourceDiscoveryRun.Status.PENDING)

    response = client.post(
        CLAIM_URL,
        data={"provider": "claude-code"},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["vocab"] == {
        "categories": [slug for slug, _ in CATEGORY],
        "regions": [slug for slug, _ in REGION],
    }


def test_claim_응답의_카테고리_어휘는_런타임에_추가한_카테고리를_담고_비활성_카테고리는_뺀다(
    client, runner_headers
):
    """core.categories.category_slugs()는 "LLM 재검증이 비활성 카테고리를
    새로 제안하지 않도록" 활성만 돌려주게 설계돼 있다(그 함수 docstring) —
    러너 vocab이 바로 그 설계 의도가 적용돼야 할 자리라 판단 갈림 없이
    active-only로 고정한다. 지금은 core.vocab.CATEGORY 정적 튜플을 그대로
    쓰고 있어 새 카테고리도, 비활성화도 반영되지 않는다 — Red 예상."""
    Category.objects.create(slug="vintage_market_runner", label="빈티지 마켓")
    concert = Category.objects.get(slug="concert")
    concert.is_active = False
    concert.save()
    SourceDiscoveryRun.objects.create(status=SourceDiscoveryRun.Status.PENDING)

    response = client.post(
        CLAIM_URL,
        data={"provider": "claude-code"},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    categories = response.json()["run"]["vocab"]["categories"]
    assert "vintage_market_runner" in categories
    assert "concert" not in categories


def test_claim은_대기_실행이_없으면_run_None을_반환한다(client, runner_headers):
    response = client.post(
        CLAIM_URL,
        data={"provider": "claude-code"},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"run": None}


def test_claim_응답에_실행에_저장된_검색어가_실린다(client, runner_headers):
    SourceDiscoveryRun.objects.create(
        status=SourceDiscoveryRun.Status.PENDING, query="하츠네 미쿠"
    )

    response = client.post(
        CLAIM_URL,
        data={"provider": "claude-code"},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    assert response.json()["run"]["query"] == "하츠네 미쿠"


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


def test_완료_요청이_보낸_시도_실패_건수가_실행에_그대로_저장된다(client, runner_headers):
    run = _make_claimed_run()
    SourceCandidate.objects.create(
        run=run,
        name="후보",
        url="https://example.com/n1",
        source_type="html",
        sample_url="https://example.com/n1/sample",
        status=SourceCandidate.Status.PROMOTED,
    )

    # 러너가 보낸 시도·실패 건수가 0이 아닌 값으로 그대로 저장되어야 한다.
    response = client.post(
        _complete_url(run.pk),
        data={
            "lease_token": "tok",
            "runner_status": "succeeded",
            "events_attempted": 5,
            "events_failed": 2,
        },
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.events_attempted == 5
    assert run.events_failed == 2


def test_완료_요청이_보낸_제외_건수가_실행에_저장된다(client, runner_headers):
    run = _make_claimed_run()

    # 러너가 정책상 정상 제외한 건수도 실행에 저장되어야 한다.
    response = client.post(
        _complete_url(run.pk),
        data={
            "lease_token": "tok",
            "runner_status": "succeeded",
            "events_attempted": 5,
            "events_failed": 2,
            "events_excluded": 3,
        },
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.events_excluded == 3


def test_완료_요청의_event_outcomes가_실행에_저장된다(client, runner_headers):
    run = _make_claimed_run()

    event_outcomes = [
        {"url": "https://example.com/e1", "outcome": "failed", "reason": "fetch_empty"},
        {"url": "https://example.com/e2", "outcome": "skipped", "reason": "known_url"},
    ]

    response = client.post(
        _complete_url(run.pk),
        data={
            "lease_token": "tok",
            "runner_status": "succeeded",
            "event_outcomes": event_outcomes,
        },
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.event_outcomes == event_outcomes


@pytest.mark.parametrize(
    "bad_item",
    [
        "x",
        {"url": "ftp://example.com/a", "outcome": "failed", "reason": "fetch_empty"},
        {
            "url": "https://example.com/" + "a" * 200,
            "outcome": "failed",
            "reason": "fetch_empty",
        },
        {"url": "https://example.com/b", "outcome": "weird", "reason": "fetch_empty"},
        {"url": "https://example.com/c", "outcome": "failed", "reason": "weird"},
        {"url": "https://example.com/d", "outcome": "created", "reason": "fetch_empty"},
    ],
    ids=[
        "dict_아님",
        "http_아닌_스킴",
        "200자_초과_URL",
        "모르는_outcome",
        "모르는_reason",
        "outcome과_reason_짝_불일치",
    ],
)
def test_event_outcomes의_잘못된_항목은_버리고_완료는_정상_처리된다(client, runner_headers, bad_item, caplog):
    run = _make_claimed_run()

    valid_item = {"url": "https://example.com/ok", "outcome": "failed", "reason": "fetch_empty"}

    with caplog.at_level(logging.WARNING, logger="drafts.discovery_runs"):
        response = client.post(
            _complete_url(run.pk),
            data={
                "lease_token": "tok",
                "runner_status": "succeeded",
                "event_outcomes": [valid_item, bad_item],
            },
            content_type="application/json",
            **runner_headers,
        )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.event_outcomes == [valid_item]
    # 후보·이벤트 모두 없음(none)이면 정상으로 합쳐진다(기존 규칙, DAR 확인).
    assert run.status == SourceDiscoveryRun.Status.SUCCEEDED
    # 버린 항목 1건(bad_item)에 대한 경고 로그가 개수와 함께 남는다.
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "dropped invalid event outcomes" in r.getMessage() and "count=1" in r.getMessage()
        for r in warning_records
    )


def test_event_outcomes를_보내지_않는_옛_러너_완료도_빈_목록으로_성공한다(client, runner_headers):
    run = _make_claimed_run()

    response = client.post(
        _complete_url(run.pk),
        data={"lease_token": "tok", "runner_status": "succeeded"},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.event_outcomes == []


def test_event_outcomes가_상한을_넘으면_20건까지만_저장된다(client, runner_headers):
    run = _make_claimed_run()

    items = [
        {"url": f"https://example.com/e{i}", "outcome": "failed", "reason": "fetch_empty"}
        for i in range(21)
    ]

    response = client.post(
        _complete_url(run.pk),
        data={
            "lease_token": "tok",
            "runner_status": "succeeded",
            "event_outcomes": items,
        },
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert len(run.event_outcomes) == 20
    assert run.event_outcomes == items[:20]


def test_event_outcomes의_URL_제어문자는_제거되어_저장된다(client, runner_headers):
    run = _make_claimed_run()

    response = client.post(
        _complete_url(run.pk),
        data={
            "lease_token": "tok",
            "runner_status": "succeeded",
            "event_outcomes": [
                {
                    "url": "https://example.com/a\x1b[31mb\x07",
                    "outcome": "failed",
                    "reason": "fetch_empty",
                }
            ],
        },
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.event_outcomes == [
        {"url": "https://example.com/a[31mb", "outcome": "failed", "reason": "fetch_empty"}
    ]


def test_실행에_없는_드래프트를_생성했다고_보고한_항목은_버려진다(client, runner_headers):
    run = _make_claimed_run()
    EventDraft.objects.create(source_url="https://example.com/real", discovery_run=run)

    response = client.post(
        _complete_url(run.pk),
        data={
            "lease_token": "tok",
            "runner_status": "succeeded",
            "event_outcomes": [
                {"url": "https://example.com/real", "outcome": "created", "reason": ""},
                {"url": "https://example.com/fake", "outcome": "created", "reason": ""},
            ],
        },
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.event_outcomes == [
        {"url": "https://example.com/real", "outcome": "created", "reason": ""}
    ]


@pytest.mark.parametrize("bad_value", ["오", None, True, ["오"]], ids=["문자열", "None", "불리언", "리스트"])
@pytest.mark.parametrize("field", ["events_attempted", "events_failed", "events_excluded"])
def test_완료_요청의_건수가_정수가_아니면_400으로_거부한다(client, runner_headers, field, bad_value):
    run = _make_claimed_run()

    response = client.post(
        _complete_url(run.pk),
        data={
            "lease_token": "tok",
            "runner_status": "succeeded",
            field: bad_value,
        },
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 400
    run.refresh_from_db()
    assert run.status == SourceDiscoveryRun.Status.CLAIMED
    assert run.finished_at is None


@pytest.mark.parametrize(
    "bad_value", ["오", {"a": 1}], ids=["문자열", "dict"]
)
def test_event_outcomes가_리스트가_아니면_400으로_거부한다(client, runner_headers, bad_value):
    run = _make_claimed_run()

    response = client.post(
        _complete_url(run.pk),
        data={
            "lease_token": "tok",
            "runner_status": "succeeded",
            "event_outcomes": bad_value,
        },
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 400
    run.refresh_from_db()
    assert run.status == SourceDiscoveryRun.Status.CLAIMED
    assert run.finished_at is None


def test_discovery_runner_스로틀_scope가_등록되어_있다(settings):
    rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["discovery_runner"]

    assert rate.endswith("/minute")


def test_러너_스로틀은_X_Forwarded_For_값과_무관하게_한_버킷으로_센다(client, runner_headers, monkeypatch, clear_cache):
    # THROTTLE_RATES는 임포트 시점에 고정되는 클래스 속성이라 설정만 바꿔서는
    # 반영되지 않는다 — 클래스 속성 자체를 직접 덮어쓴다.
    monkeypatch.setattr(
        RunnerTokenThrottle, "THROTTLE_RATES", {"discovery_runner": "2/minute"}
    )

    first_response = client.post(
        HEARTBEAT_URL,
        data={},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="1.1.1.1",
        **runner_headers,
    )
    second_response = client.post(
        HEARTBEAT_URL,
        data={},
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="2.2.2.2",
        **runner_headers,
    )
    third_response = client.post(
        HEARTBEAT_URL,
        data={},
        content_type="application/json",
        **runner_headers,
    )

    assert first_response.status_code == 204
    assert second_response.status_code == 204
    # 세 요청이 서로 다른 X-Forwarded-For(또는 헤더 없음)를 줬는데도 세 번째가
    # 막힌다는 것이 한 버킷으로 세고 있다는 증거다.
    assert third_response.status_code == 429
