"""Tests for the DRAFT_LLM_EXTRACTION_ENABLED wiring in
drafts.services.create_draft_from_url.

Mocks drafts.services.extract_event_fields_llm — never core.llm/anthropic
directly — services owns the flag branch, not the LLM call itself (that
contract is covered by tests/test_draft_llm_extraction.py).
"""
import pytest
from django.test import override_settings

from drafts.extraction import EmptyExtractionError
from drafts.models import EventDraft
from drafts.services import DraftCreationEmptyExtractionError, create_draft_from_url


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_flag_enabled_uses_llm_extractor_with_parsed_raw_fields(monkeypatch, sample_extraction):
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

    draft = create_draft_from_url("https://example.com/event")

    assert calls == [(sample_extraction["raw_title"], sample_extraction["raw_text"])]
    assert draft.confidence == 0.83
    assert draft.extraction_method == "llm"
    assert draft.extracted_category == "popup_store"
    assert draft.extracted_work_title == "IVE"


@pytest.mark.django_db
def test_flag_disabled_never_calls_llm_extractor(monkeypatch, fail_if_called, sample_extraction):
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

    draft = create_draft_from_url("https://example.com/event")

    assert draft.extracted_title == sample_extraction["raw_title"]


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_flag_enabled_empty_extraction_raises_without_calling_llm(monkeypatch, fail_if_called):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html></html>")

    def raise_empty(html):
        raise EmptyExtractionError

    monkeypatch.setattr("drafts.services.parse_raw_fields", raise_empty)
    monkeypatch.setattr("drafts.services.extract_event_fields_llm", fail_if_called)

    with pytest.raises(DraftCreationEmptyExtractionError):
        create_draft_from_url("https://example.com/event")


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_flag_enabled_heuristic_fallback_result_is_recorded_as_is(monkeypatch, sample_extraction):
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

    draft = create_draft_from_url("https://example.com/event")

    assert draft.confidence is None
    assert draft.extraction_method == "heuristic"


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_flag_enabled_ignores_is_event_key_in_llm_result(monkeypatch, sample_extraction):
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

    draft = create_draft_from_url("https://example.com/event")

    assert draft.id is not None
    assert not hasattr(EventDraft, "is_event")


@pytest.mark.django_db
def test_flag_disabled_defaults_extraction_method_heuristic_and_confidence_none(monkeypatch, sample_extraction):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Sample</title></html>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": sample_extraction["raw_title"], "raw_text": sample_extraction["raw_text"]},
    )

    draft = create_draft_from_url("https://example.com/event")

    assert draft.extraction_method == EventDraft.ExtractionMethod.HEURISTIC
    assert draft.confidence is None


@pytest.mark.django_db
@override_settings(DRAFT_LLM_EXTRACTION_ENABLED=True)
def test_create_draft_from_fields_never_calls_llm_even_when_flag_enabled(monkeypatch, fail_if_called):
    from drafts.services import create_draft_from_fields

    monkeypatch.setattr("drafts.services.extract_event_fields_llm", fail_if_called)

    draft = create_draft_from_fields(source_url="https://example.com/manual-report", title="Manual")

    assert draft.extracted_title == "Manual"
