"""drafts.llm_extraction의 도구 스키마가 호출 시점마다 카테고리 어휘를 다시
읽는지 검증한다(트랙 27 5단계 Phase A, D-02).

tests/drafts/test_draft_llm_extraction.py는 pytest.mark.unit(DB 없음)이라
DB로 Category를 추가해야 하는 이 시나리오는 별도 파일로 분리했다.

drafts/llm_extraction.py:28의 `CATEGORY_SLUGS = [slug for slug, _ in CATEGORY]`가
모듈 임포트 시점 스냅샷인 한, 런타임에 추가한 카테고리는 이 테스트에서
스키마 enum에 나타날 수 없다 — 그래서 Red다.
"""
import pytest

from core.models import Category
from core.vocab import CATEGORY, REGION
from drafts.llm_extraction import extract_event_fields_llm

pytestmark = [pytest.mark.django_db, pytest.mark.domain]

HIGH_CONFIDENCE = {
    "title": 0.9,
    "summary": 0.9,
    "category": 0.9,
    "region": 0.9,
    "start_date": 0.9,
    "end_date": 0.9,
    "work_title": 0.9,
    "location_name": 0.9,
}


def _fake_call_tool(responses):
    calls = []
    remaining = list(responses)

    def fake(**kwargs):
        calls.append(kwargs)
        return remaining.pop(0)

    return fake, calls


def test_LLM_추출_스키마는_호출_시점에_카테고리_어휘를_다시_읽는다(monkeypatch):
    새_슬러그 = "runtime_added_category"
    Category.objects.create(slug=새_슬러그, label="런타임추가카테고리")

    response = {
        "is_event": True,
        "title": "제목",
        "summary": "요약",
        "category": 새_슬러그,
        "region": "seoul",
        "start_date": "",
        "end_date": "",
        "work_title": "",
        "location_name": "",
        "field_confidence": dict(HIGH_CONFIDENCE),
    }
    fake, calls = _fake_call_tool([response])
    monkeypatch.setattr("drafts.llm_extraction.call_tool", fake)

    extract_event_fields_llm("제목", "본문")

    schema = calls[0]["tool_schema"]
    assert 새_슬러그 in schema["properties"]["category"]["enum"]


def test_도구_스키마는_전체_카테고리와_지역_슬러그를_포함한다(monkeypatch, sample_extraction):
    """tests/drafts/test_draft_llm_extraction.py에서 옮겨왔다(트랙 27 5단계) —
    _tool_schema()의 category enum이 core.categories.category_slugs를 통해
    실제 DB(Category)를 보므로, DB 없이는 이 시나리오를 의미 있게 고정할 수
    없다(고정 목록으로 monkeypatch하면 이 어서션이 항상 통과해 무의미해진다).
    region enum은 여전히 core.vocab.REGION 상수라 DB가 필요 없지만, 두 필드가
    같은 스키마 호출 한 번에서 나오는 걸 보는 편이 자연스러워 같이 둔다."""
    response = {
        "is_event": True,
        "title": "IVE Popup Store",
        "summary": "IVE 팝업 스토어 안내",
        "category": "popup_store",
        "region": "seoul",
        "start_date": "2026-07-01",
        "end_date": "2026-07-20",
        "work_title": "IVE",
        "location_name": "홍대",
        "field_confidence": dict(HIGH_CONFIDENCE),
    }
    fake, calls = _fake_call_tool([response])
    monkeypatch.setattr("drafts.llm_extraction.call_tool", fake)

    extract_event_fields_llm(sample_extraction["raw_title"], sample_extraction["raw_text"])

    schema = calls[0]["tool_schema"]
    category_slugs = [slug for slug, _ in CATEGORY]
    region_slugs = [slug for slug, _ in REGION]
    for slug in category_slugs:
        assert slug in schema["properties"]["category"]["enum"]
    for slug in region_slugs:
        assert slug in schema["properties"]["region"]["enum"]
