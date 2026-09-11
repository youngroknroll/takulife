"""drafts.agent_drafts — 러너가 제출하는 키워드 탐색 드래프트 페이로드의
schema 검증 unit 테스트. 페이로드는 §E 계약(계획서 290~292행의 v2 계약 +
트랙 30 추가 4필드 platform·judgment·official_basis·source_name)을 따른다.
이 파일은 IG-01부터 순차로 계약을 쌓는다."""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from drafts.agent_drafts import (
    MAX_EVENTS_PER_RUN,
    AgentDraftSchemaError,
    EventLimitExceededError,
    parse_agent_draft_payload,
    submit_agent_draft,
)
from drafts.discovery_runs import LeaseInvalidError, renew_lease
from drafts.models import EventDraft, SourceDiscoveryRun
from drafts.robots import RobotsCheckResult
from drafts.url_safety import UnsafeFetchUrlError


pytestmark = pytest.mark.unit


def _valid_payload():
    return {
        "source_url": "https://example.com/event",
        "raw_title": "코믹월드 공지",
        "raw_text": "코믹월드 공지 원문입니다.",
        "fields": {
            "title": "코믹월드",
            "work_title": "",
            "category": "popup_store",
            "region": "seoul",
            "location_name": "코엑스",
            "start_date": "2026-10-01",
            "end_date": "2026-10-02",
            "summary": "코믹월드 팝업스토어 공지입니다.",
        },
        "confidence": 0.8,
        "note": "공식 공지 원문 인용",
        "platform": "web",
        "judgment": "official",
        "official_basis": "공식 도메인",
        "source_name": "코믹월드 공식",
    }


def test_필수_키가_빠진_러너_드래프트_페이로드는_schema_오류로_거부된다():
    payload = _valid_payload()
    del payload["source_url"]

    cleaned, stage = parse_agent_draft_payload(payload=payload)

    assert stage == "schema"


def _payload_스킴_위반():
    payload = _valid_payload()
    payload["source_url"] = "ftp://example.com/x"
    return payload


def _payload_길이_초과():
    payload = _valid_payload()
    payload["source_url"] = "https://example.com/" + "a" * 200
    return payload


@pytest.mark.parametrize(
    "make_payload",
    [_payload_스킴_위반, _payload_길이_초과],
    ids=["스킴_위반", "길이_초과"],
)
def test_url_스킴이나_길이가_위반된_이벤트_후보는_schema_오류로_거부된다(make_payload):
    payload = make_payload()

    cleaned, stage = parse_agent_draft_payload(payload=payload)

    assert stage == "schema"


def _payload_카테고리만_위반():
    payload = _valid_payload()
    payload["fields"]["category"] = "콘서트"
    return payload


def _payload_지역만_위반():
    payload = _valid_payload()
    payload["fields"]["region"] = "제주"
    return payload


def _payload_둘_다_위반():
    payload = _valid_payload()
    payload["fields"]["category"] = "콘서트"
    payload["fields"]["region"] = "제주"
    return payload


@pytest.mark.parametrize(
    "make_payload",
    [_payload_카테고리만_위반, _payload_지역만_위반, _payload_둘_다_위반],
    ids=["카테고리만", "지역만", "둘_다"],
)
def test_어휘_밖_카테고리와_지역은_빈_값으로_바뀌고_메모에_원값_사유가_남는다(make_payload):
    payload = make_payload()

    cleaned, stage = parse_agent_draft_payload(payload=payload)

    assert stage is None
    if payload["fields"]["category"] == "콘서트":
        assert cleaned["fields"]["category"] == ""
        assert "카테고리 값 불일치" in cleaned["note"]
        assert "콘서트" in cleaned["note"]
    if payload["fields"]["region"] == "제주":
        assert cleaned["fields"]["region"] == ""
        assert "지역 값 불일치" in cleaned["note"]
        assert "제주" in cleaned["note"]


def _payload_confidence_상한_초과():
    payload = _valid_payload()
    payload["confidence"] = 1.5
    return payload


def _payload_confidence_하한_미만():
    payload = _valid_payload()
    payload["confidence"] = -0.1
    return payload


def _payload_confidence_타입_위반():
    payload = _valid_payload()
    payload["confidence"] = "높음"
    return payload


@pytest.mark.parametrize(
    "make_payload",
    [_payload_confidence_상한_초과, _payload_confidence_하한_미만, _payload_confidence_타입_위반],
    ids=["상한_초과", "하한_미만", "타입_위반"],
)
def test_범위_밖이거나_숫자가_아닌_confidence는_null로_비워지고_메모에_사유가_남는다(make_payload):
    payload = make_payload()

    cleaned, stage = parse_agent_draft_payload(payload=payload)

    assert stage is None
    assert cleaned["confidence"] is None
    assert "confidence 값 불일치" in cleaned["note"]


def test_시작일이_종료일보다_늦으면_두_날짜가_비워지고_메모에_사유가_남는다():
    payload = _valid_payload()
    payload["fields"]["start_date"] = "2026-09-20"
    payload["fields"]["end_date"] = "2026-09-01"

    cleaned, stage = parse_agent_draft_payload(payload=payload)

    assert stage is None
    assert cleaned["fields"]["start_date"] is None
    assert cleaned["fields"]["end_date"] is None
    assert "기간 역전" in cleaned["note"]


class _AllowAllRobots:
    def check(self, url):
        return RobotsCheckResult(True, None)


@pytest.fixture
def _neutralize_server_recheck(monkeypatch):
    """이 파일의 도메인 테스트(IG-04·IG-05·IG-18)는 서버 재확인(KW-07)을 타지
    않는다 — 네트워크가 관심사가 아니므로 항상 통과하도록 무력화한다."""
    monkeypatch.setattr(
        "drafts.agent_drafts.validate_fetch_url", lambda url, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("drafts.agent_drafts.RobotsChecker", _AllowAllRobots)
    monkeypatch.setattr(
        "drafts.agent_drafts.fetch_html", lambda url, **kwargs: "<html></html>"
    )


def _make_claimed_run():
    return SourceDiscoveryRun.objects.create(
        status=SourceDiscoveryRun.Status.CLAIMED,
        lease_token="tok",
        lease_expires_at=timezone.now() + timedelta(seconds=900),
        lease_count=1,
    )


def _make_pending_run():
    return SourceDiscoveryRun.objects.create(status=SourceDiscoveryRun.Status.PENDING)


def _make_run_with_expired_lease():
    return SourceDiscoveryRun.objects.create(
        status=SourceDiscoveryRun.Status.CLAIMED,
        lease_token="tok",
        lease_expires_at=timezone.now() - timedelta(seconds=1),
        lease_count=1,
    )


@pytest.mark.django_db
@pytest.mark.domain
@pytest.mark.parametrize(
    "make_run",
    [_make_pending_run, _make_run_with_expired_lease],
    ids=["미클레임", "만료"],
)
def test_임대가_없거나_만료된_실행으로의_제출은_거부된다(make_run):
    run = make_run()
    payload = _valid_payload()

    with pytest.raises(LeaseInvalidError):
        submit_agent_draft(run_id=run.pk, lease_token="아무값", payload=payload)

    assert EventDraft.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.domain
def test_유효_페이로드를_제출하면_출처명_캡션_메모_기간_LLM추출_표시를_가진_검토대기_드래프트가_생성된다(_neutralize_server_recheck):
    run = _make_claimed_run()
    payload = {
        "source_url": "https://official-site.example.com/event",
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

    draft, created = submit_agent_draft(run_id=run.pk, lease_token="tok", payload=payload)

    assert created is True
    assert EventDraft.objects.count() == 1
    draft = EventDraft.objects.get()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.source_name == "공식 홈페이지"
    assert draft.raw_title == "무제 팝업 안내"
    assert draft.raw_text == "원문 캡션..."
    # "승인 가능" 조건: 제목·공식 URL·카테고리·지역·장소명이 비어 있지 않아야 한다.
    assert draft.extracted_title == "하츠네 미쿠 팝업스토어"
    assert draft.extracted_category == "popup_store"
    assert draft.extracted_region == "seoul"
    assert draft.extracted_location_name == "용산 아이파크몰"
    assert draft.extracted_start_date == date(2026, 9, 1)
    assert draft.extracted_end_date == date(2026, 9, 22)
    assert draft.confidence == 0.9
    assert draft.extraction_method == EventDraft.ExtractionMethod.LLM
    assert draft.intake_note == ""
    assert draft.discovery_run == run


def _valid_payload_for_submit(source_url):
    payload = {
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
    return payload


@pytest.mark.django_db
@pytest.mark.domain
@pytest.mark.parametrize("same_run", [True, False], ids=["같은_실행", "다른_실행"])
def test_같은_이벤트_URL을_다시_제출하면_새_드래프트_없이_기존_id를_돌려준다(same_run, _neutralize_server_recheck):
    run_a = _make_claimed_run()
    source_url = "https://official-site.example.com/event"
    existing_draft, _ = submit_agent_draft(
        run_id=run_a.pk, lease_token="tok", payload=_valid_payload_for_submit(source_url)
    )

    submitting_run = run_a if same_run else _make_claimed_run()

    draft, created = submit_agent_draft(
        run_id=submitting_run.pk,
        lease_token="tok",
        payload=_valid_payload_for_submit(source_url),
    )

    assert created is False
    assert draft.pk == existing_draft.pk
    assert EventDraft.objects.count() == 1


def _renew_lease_before_submit(run):
    renew_lease(run=run)


def _keep_initial_lease(run):
    pass


@pytest.mark.django_db
@pytest.mark.domain
@pytest.mark.parametrize(
    "before_submit",
    [_keep_initial_lease, _renew_lease_before_submit],
    ids=["최초_임대", "재임대_후"],
)
def test_실행당_이벤트_상한을_넘는_제출은_거부되고_드래프트가_생성되지_않는다(before_submit, _neutralize_server_recheck):
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

    before_submit(run)

    with pytest.raises(EventLimitExceededError):
        submit_agent_draft(
            run_id=run.pk,
            lease_token="tok",
            payload=_valid_payload_for_submit("https://new.example.com/event"),
        )

    assert EventDraft.objects.filter(discovery_run=run).count() == MAX_EVENTS_PER_RUN


def _patch_일반_웹_재확인(monkeypatch, fail_if_called):
    fetch_calls = []

    def fake_fetch_html(url, **kwargs):
        fetch_calls.append(url)
        return "<html></html>"

    monkeypatch.setattr("drafts.agent_drafts.fetch_html", fake_fetch_html)
    monkeypatch.setattr(
        "drafts.agent_drafts.validate_fetch_url", lambda url, **kwargs: "1.1.1.1"
    )
    monkeypatch.setattr("drafts.agent_drafts.RobotsChecker", _AllowAllRobots)
    return {
        "source_url": "https://official-site.example.com/event",
        "platform": "web",
        "fetch_calls": fetch_calls,
        "unsafe": False,
    }


def _patch_인스타_fetch_미호출(monkeypatch, fail_if_called):
    monkeypatch.setattr("drafts.agent_drafts.fetch_html", fail_if_called)
    return {
        "source_url": "https://www.instagram.com/p/Dck7ZVUoG4i/",
        "platform": "instagram",
        "fetch_calls": None,
        "unsafe": False,
    }


def _patch_안전하지_않은_URL_거부(monkeypatch, fail_if_called):
    def raise_unsafe(url, **kwargs):
        raise UnsafeFetchUrlError

    monkeypatch.setattr("drafts.agent_drafts.validate_fetch_url", raise_unsafe)
    return {
        "source_url": "https://official-site.example.com/event",
        "platform": "web",
        "fetch_calls": None,
        "unsafe": True,
    }


@pytest.mark.django_db
@pytest.mark.contract
@pytest.mark.parametrize(
    "setup",
    [_patch_일반_웹_재확인, _patch_인스타_fetch_미호출, _patch_안전하지_않은_URL_거부],
    ids=["일반_웹_재확인", "인스타_fetch_미호출", "안전하지_않은_URL_거부"],
)
def test_일반_웹_URL_제출은_서버가_존재를_재확인하고_인스타_URL_제출은_fetch를_호출하지_않으며_안전하지_않은_URL은_거부된다(
    setup, monkeypatch, fail_if_called
):
    context = setup(monkeypatch, fail_if_called)

    run = _make_claimed_run()
    payload = _valid_payload_for_submit(context["source_url"])
    payload["platform"] = context["platform"]

    if context["unsafe"]:
        with pytest.raises(UnsafeFetchUrlError):
            submit_agent_draft(run_id=run.pk, lease_token="tok", payload=payload)
        assert EventDraft.objects.count() == 0
        return

    draft, created = submit_agent_draft(run_id=run.pk, lease_token="tok", payload=payload)

    assert created is True
    assert EventDraft.objects.count() == 1
    if context["fetch_calls"] is not None:
        assert context["fetch_calls"] == [context["source_url"]]
        assert draft.raw_text != "<html></html>"


@pytest.mark.django_db
@pytest.mark.domain
@pytest.mark.parametrize(
    "judgment, expected_prefix",
    [
        ("unofficial", "탐색 판단: 비공식 — 비공식 팬 계정으로 추정됨"),
        ("unclear", "탐색 판단: 불명 — 비공식 팬 계정으로 추정됨"),
    ],
    ids=["비공식", "불명"],
)
def test_비공식_판단_이벤트는_메모_앞머리에_판단과_근거가_붙어_저장된다(
    judgment, expected_prefix, _neutralize_server_recheck
):
    run = _make_claimed_run()
    payload = _valid_payload_for_submit("https://official-site.example.com/event")
    payload["judgment"] = judgment
    payload["official_basis"] = "비공식 팬 계정으로 추정됨"

    draft, created = submit_agent_draft(run_id=run.pk, lease_token="tok", payload=payload)

    assert draft.intake_note.startswith(expected_prefix)


@pytest.mark.django_db
@pytest.mark.domain
def test_비공식_판단_이벤트에_원본_메모가_있으면_판단_접두_뒤에_원본이_남는다(_neutralize_server_recheck):
    run = _make_claimed_run()
    payload = _valid_payload_for_submit("https://official-site.example.com/event")
    payload["judgment"] = "unofficial"
    payload["official_basis"] = "비공식 팬 계정으로 추정됨"
    payload["note"] = "원본 메모"

    draft, created = submit_agent_draft(run_id=run.pk, lease_token="tok", payload=payload)

    expected_prefix = "탐색 판단: 비공식 — 비공식 팬 계정으로 추정됨"
    assert draft.intake_note.startswith(expected_prefix)
    assert draft.intake_note == expected_prefix + "\n원본 메모"


@pytest.mark.parametrize(
    "source_url, expected_url",
    [
        (
            "https://official-site.example.com/event?utm_source=twitter&fbclid=abc123",
            "https://official-site.example.com/event",
        ),
        (
            "https://official-site.example.com/event?id=123&utm_campaign=fall",
            "https://official-site.example.com/event?id=123",
        ),
        (
            "https://official-site.example.com/event?id=123&lang=ko",
            "https://official-site.example.com/event?id=123&lang=ko",
        ),
    ],
    ids=["추적_파라미터만", "의미_있는_쿼리_혼재", "추적_없음"],
)
def test_source_url의_알려진_추적_파라미터만_제거되고_그_외_쿼리스트링과_경로는_보존된다(
    source_url, expected_url
):
    payload = _valid_payload()
    payload["source_url"] = source_url

    cleaned, stage = parse_agent_draft_payload(payload=payload)

    assert stage is None
    assert cleaned["source_url"] == expected_url


@pytest.mark.django_db
@pytest.mark.domain
def test_스키마_위반_페이로드를_제출하면_AgentDraftSchemaError로_거부되고_아무것도_생성되지_않는다(
    _neutralize_server_recheck,
):
    run = _make_claimed_run()
    payload = _valid_payload_for_submit("https://official-site.example.com/event")
    del payload["fields"]

    with pytest.raises(AgentDraftSchemaError):
        submit_agent_draft(run_id=run.pk, lease_token="tok", payload=payload)

    assert EventDraft.objects.count() == 0
