"""drafts.agent_drafts — 러너가 제출하는 키워드 탐색 드래프트 페이로드의
schema 검증 unit 테스트. 페이로드는 §E 계약(계획서 290~292행의 v2 계약 +
트랙 30 추가 4필드 platform·judgment·official_basis·source_name)을 따른다.
이 파일은 IG-01부터 순차로 계약을 쌓는다."""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from drafts.agent_drafts import parse_agent_draft_payload, submit_agent_draft
from drafts.discovery_runs import LeaseInvalidError
from drafts.models import EventDraft, SourceDiscoveryRun


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
def test_유효_페이로드를_제출하면_출처명_캡션_메모_기간_LLM추출_표시를_가진_검토대기_드래프트가_생성된다():
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

    submit_agent_draft(run_id=run.pk, lease_token="tok", payload=payload)

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
