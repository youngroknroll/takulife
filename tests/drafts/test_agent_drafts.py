"""drafts.agent_drafts — 러너가 제출하는 키워드 탐색 드래프트 페이로드의
schema 검증 unit 테스트. 페이로드는 §E 계약(계획서 290~292행의 v2 계약 +
트랙 30 추가 4필드 platform·judgment·official_basis·source_name)을 따른다.
이 파일은 IG-01부터 순차로 계약을 쌓는다."""
import pytest

from drafts.agent_drafts import parse_agent_draft_payload


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
