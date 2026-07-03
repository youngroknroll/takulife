"""Tests for the eval_extraction management command.

Golden set = approved drafts with non-empty raw_text (drafts created before
raw_text was captured, or manually-reported drafts via create_draft_from_fields,
have no raw_text to re-run extraction against — excluded). Mocks the extractor
functions at the command's import location, never real LLM/anthropic calls.
"""
import pytest
from django.core.management import call_command

from drafts.models import EventDraft


def _fail_if_called(*args, **kwargs):
    raise AssertionError("this extractor must not be called")


def _make_draft(**overrides):
    defaults = {
        "source_url": "https://example.com/event",
        "raw_title": "IVE Popup Store",
        "raw_text": "서울 홍대 2026-07-01 팝업",
        "extracted_category": "popup_store",
        "extracted_region": "seoul",
        "review_status": EventDraft.ReviewStatus.PENDING,
    }
    defaults.update(overrides)
    return EventDraft.objects.create(**defaults)


@pytest.mark.django_db
def test_no_approved_drafts_reports_empty_golden_set_without_error(capsys):
    call_command("eval_extraction")

    output = capsys.readouterr().out
    assert "0" in output


@pytest.mark.django_db
def test_only_pending_and_rejected_drafts_yield_empty_golden_set(capsys):
    _make_draft(source_url="https://example.com/pending", review_status=EventDraft.ReviewStatus.PENDING)
    _make_draft(source_url="https://example.com/rejected", review_status=EventDraft.ReviewStatus.REJECTED)

    call_command("eval_extraction")

    output = capsys.readouterr().out
    assert "0" in output


@pytest.mark.django_db
def test_excludes_approved_drafts_without_raw_text(monkeypatch, capsys):
    _make_draft(
        source_url="https://example.com/no-raw-text",
        raw_title="",
        raw_text="",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )
    included = _make_draft(
        source_url="https://example.com/with-raw-text",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    calls = []

    def spy(raw_title, raw_text):
        calls.append((raw_title, raw_text))
        return {"extracted_category": "popup_store", "extracted_region": "seoul"}

    monkeypatch.setattr("drafts.management.commands.eval_extraction.extract_event_fields_llm", spy)

    call_command("eval_extraction")

    assert calls == [(included.raw_title, included.raw_text)]


@pytest.mark.django_db
def test_default_run_uses_llm_extractor(monkeypatch, capsys):
    _make_draft(review_status=EventDraft.ReviewStatus.APPROVED)
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_heuristic", _fail_if_called
    )
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_llm",
        lambda raw_title, raw_text: {"extracted_category": "popup_store", "extracted_region": "seoul"},
    )

    call_command("eval_extraction")


@pytest.mark.django_db
def test_heuristic_flag_uses_heuristic_extractor_only(monkeypatch, capsys):
    _make_draft(review_status=EventDraft.ReviewStatus.APPROVED)
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_llm", _fail_if_called
    )
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_heuristic",
        lambda raw_title, raw_text: {"extracted_category": "popup_store", "extracted_region": "seoul"},
    )

    call_command("eval_extraction", "--heuristic")


@pytest.mark.django_db
def test_perfect_match_report_includes_field_names_and_accuracy(monkeypatch, capsys):
    _make_draft(review_status=EventDraft.ReviewStatus.APPROVED)
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_llm",
        lambda raw_title, raw_text: {"extracted_category": "popup_store", "extracted_region": "seoul"},
    )

    call_command("eval_extraction")

    output = capsys.readouterr().out
    assert "category" in output
    assert "region" in output
    assert "1.0" in output or "100" in output


@pytest.mark.django_db
def test_limit_option_caps_golden_set_size_and_extractor_call_count(monkeypatch, capsys):
    for i in range(3):
        _make_draft(source_url=f"https://example.com/approved-{i}", review_status=EventDraft.ReviewStatus.APPROVED)

    calls = []

    def spy(raw_title, raw_text):
        calls.append((raw_title, raw_text))
        return {"extracted_category": "popup_store", "extracted_region": "seoul"}

    monkeypatch.setattr("drafts.management.commands.eval_extraction.extract_event_fields_llm", spy)

    call_command("eval_extraction", "--limit", "2")

    assert len(calls) == 2
