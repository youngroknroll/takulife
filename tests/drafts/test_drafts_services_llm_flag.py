"""drafts.services.create_draft_from_url의 DRAFT_LLM_EXTRACTION_ENABLED 배선
테스트. core.llm/anthropic이 아니라 drafts.services.extract_event_fields_llm을
모킹한다 — services는 플래그 분기만 책임지고, LLM 호출 자체는
tests/test_draft_llm_extraction.py가 검증한다."""
import pytest
from django.test import override_settings

from drafts.extraction import EmptyExtractionError
from drafts.models import EventDraft
from drafts.services import DraftCreationEmptyExtractionError, create_draft_from_url

pytestmark = pytest.mark.domain


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_LLM_추출_플래그가_켜지면_파싱된_원문_필드로_LLM_추출기를_호출한다(monkeypatch, sample_extraction):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Sample</title></html>")
    monkeypatch.setattr(
        "drafts.services.parse_raw_fields",
        lambda html: {"raw_title": sample_extraction["raw_title"], "raw_text": sample_extraction["raw_text"]},
    )

    calls = []

    def spy(raw_title, raw_text):
        calls.append((raw_title, raw_text))
        return {
            "raw_title": raw_title,
            "raw_text": raw_text,
            "extracted_title": "IVE Popup Store",
            "extracted_summary": "IVE 팝업 스토어 안내",
            "extracted_category": "popup_store",
            "extracted_region": "seoul",
            "extracted_start_date": None,
            "extracted_end_date": None,
            "extracted_work_title": "IVE",
            "extracted_location_name": "홍대",
            "confidence": 0.83,
            "extraction_method": "llm",
            "is_event": True,
        }

    monkeypatch.setattr("drafts.services.extract_event_fields_llm", spy)

    draft = create_draft_from_url(source_url="https://example.com/event")

    assert calls == [(sample_extraction["raw_title"], sample_extraction["raw_text"])]
    assert draft.confidence == 0.83
    assert draft.extraction_method == "llm"
    assert draft.extracted_category == "popup_store"
    assert draft.extracted_work_title == "IVE"


@pytest.mark.django_db
def test_LLM_추출_플래그가_꺼지면_LLM_추출기를_호출하지_않는다(monkeypatch, fail_if_called, sample_extraction):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Sample</title></html>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {
            "raw_title": sample_extraction["raw_title"],
            "raw_text": sample_extraction["raw_text"],
            "extracted_title": sample_extraction["raw_title"],
        },
    )
    monkeypatch.setattr("drafts.services.extract_event_fields_llm", fail_if_called)

    draft = create_draft_from_url(source_url="https://example.com/event")

    assert draft.extracted_title == sample_extraction["raw_title"]


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_원문_파싱이_비어있으면_LLM_추출기_호출_없이_추출_실패_예외를_던진다(monkeypatch, fail_if_called):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html></html>")

    def raise_empty(html):
        raise EmptyExtractionError

    monkeypatch.setattr("drafts.services.parse_raw_fields", raise_empty)
    monkeypatch.setattr("drafts.services.extract_event_fields_llm", fail_if_called)

    with pytest.raises(DraftCreationEmptyExtractionError):
        create_draft_from_url(source_url="https://example.com/event")


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_LLM_추출기가_휴리스틱으로_대체한_결과를_그대로_기록한다(monkeypatch, sample_extraction):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Sample</title></html>")
    monkeypatch.setattr(
        "drafts.services.parse_raw_fields",
        lambda html: {"raw_title": sample_extraction["raw_title"], "raw_text": sample_extraction["raw_text"]},
    )
    monkeypatch.setattr(
        "drafts.services.extract_event_fields_llm",
        lambda raw_title, raw_text: {
            "raw_title": raw_title,
            "raw_text": raw_text,
            "extracted_title": raw_title,
            "extracted_summary": "",
            "extracted_category": "",
            "extracted_region": "",
            "extracted_start_date": None,
            "extracted_end_date": None,
            "extracted_work_title": "",
            "extracted_location_name": "",
            "confidence": None,
            "extraction_method": "heuristic",
            "is_event": True,
        },
    )

    draft = create_draft_from_url(source_url="https://example.com/event")

    assert draft.confidence is None
    assert draft.extraction_method == "heuristic"


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_LLM_결과의_is_event_키는_드래프트_생성에_영향을_주지_않는다(monkeypatch, sample_extraction):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Sample</title></html>")
    monkeypatch.setattr(
        "drafts.services.parse_raw_fields",
        lambda html: {"raw_title": sample_extraction["raw_title"], "raw_text": sample_extraction["raw_text"]},
    )
    monkeypatch.setattr(
        "drafts.services.extract_event_fields_llm",
        lambda raw_title, raw_text: {
            "raw_title": raw_title,
            "raw_text": raw_text,
            "extracted_title": raw_title,
            "extracted_summary": "",
            "extracted_category": "",
            "extracted_region": "",
            "extracted_start_date": None,
            "extracted_end_date": None,
            "extracted_work_title": "",
            "extracted_location_name": "",
            "confidence": 0.5,
            "extraction_method": "llm",
            "is_event": False,
        },
    )

    draft = create_draft_from_url(source_url="https://example.com/event")

    assert draft.id is not None
    assert not hasattr(EventDraft, "is_event")


@pytest.mark.django_db
def test_LLM_추출_플래그가_꺼지면_추출_방식과_신뢰도가_기본값으로_설정된다(monkeypatch, sample_extraction):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Sample</title></html>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": sample_extraction["raw_title"], "raw_text": sample_extraction["raw_text"]},
    )

    draft = create_draft_from_url(source_url="https://example.com/event")

    assert draft.extraction_method == EventDraft.ExtractionMethod.HEURISTIC
    assert draft.confidence is None


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_직접_등록_경로는_LLM_추출_플래그가_켜져도_LLM_추출기를_호출하지_않는다(monkeypatch, fail_if_called):
    from drafts.services import create_draft_from_fields

    monkeypatch.setattr("drafts.services.extract_event_fields_llm", fail_if_called)

    draft = create_draft_from_fields(source_url="https://example.com/manual-report", title="Manual")

    assert draft.extracted_title == "Manual"
