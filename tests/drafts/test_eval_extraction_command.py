"""Tests for the eval_extraction management command.

Golden set = approved drafts with non-empty raw_text (drafts created before
raw_text was captured, or manually-reported drafts via create_draft_from_fields,
have no raw_text to re-run extraction against — excluded). Mocks the extractor
functions at the command's import location, never real LLM/anthropic calls.
"""
import pytest
from django.core.management import call_command

from drafts.models import EventDraft

pytestmark = pytest.mark.domain


def _make_draft(make_draft, **overrides):
    defaults = {
        "source_url": "https://example.com/event",
        "raw_title": "IVE Popup Store",
        "raw_text": "서울 홍대 2026-07-01 팝업",
        "extracted_category": "popup_store",
        "extracted_region": "seoul",
        "review_status": EventDraft.ReviewStatus.PENDING,
    }
    defaults.update(overrides)
    return make_draft(**defaults)


@pytest.mark.django_db
def test_승인된_드래프트가_없으면_오류_없이_빈_평가셋을_보고한다(capsys):
    call_command("eval_extraction")

    output = capsys.readouterr().out
    assert "0" in output


@pytest.mark.django_db
def test_대기_거절_드래프트만_있으면_평가셋이_비어있다(capsys, make_draft):
    _make_draft(make_draft, source_url="https://example.com/pending", review_status=EventDraft.ReviewStatus.PENDING)
    _make_draft(make_draft, source_url="https://example.com/rejected", review_status=EventDraft.ReviewStatus.REJECTED)

    call_command("eval_extraction")

    output = capsys.readouterr().out
    assert "0" in output


@pytest.mark.django_db
def test_원문이_없는_승인_드래프트는_평가셋에서_제외된다(monkeypatch, capsys, make_draft):
    _make_draft(make_draft, 
        source_url="https://example.com/no-raw-text",
        raw_title="",
        raw_text="",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )
    included = _make_draft(make_draft, 
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
def test_기본_실행은_휴리스틱_없이_LLM_추출기를_사용한다(monkeypatch, capsys, make_draft, fail_if_called):
    _make_draft(make_draft, review_status=EventDraft.ReviewStatus.APPROVED)
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_heuristic", fail_if_called
    )
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_llm",
        lambda raw_title, raw_text: {"extracted_category": "popup_store", "extracted_region": "seoul"},
    )

    call_command("eval_extraction")


@pytest.mark.django_db
def test_heuristic_플래그를_주면_LLM_없이_휴리스틱_추출기만_사용한다(monkeypatch, capsys, make_draft, fail_if_called):
    _make_draft(make_draft, review_status=EventDraft.ReviewStatus.APPROVED)
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_llm", fail_if_called
    )
    monkeypatch.setattr(
        "drafts.management.commands.eval_extraction.extract_event_fields_heuristic",
        lambda raw_title, raw_text: {"extracted_category": "popup_store", "extracted_region": "seoul"},
    )

    call_command("eval_extraction", "--heuristic")


@pytest.mark.django_db
def test_완전히_일치하면_보고서에_필드명과_정확도가_포함된다(monkeypatch, capsys, make_draft):
    _make_draft(make_draft, review_status=EventDraft.ReviewStatus.APPROVED)
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
def test_limit_옵션은_평가셋_크기와_추출기_호출_횟수를_제한한다(monkeypatch, capsys, make_draft):
    for i in range(3):
        _make_draft(make_draft, source_url=f"https://example.com/approved-{i}", review_status=EventDraft.ReviewStatus.APPROVED)

    calls = []

    def spy(raw_title, raw_text):
        calls.append((raw_title, raw_text))
        return {"extracted_category": "popup_store", "extracted_region": "seoul"}

    monkeypatch.setattr("drafts.management.commands.eval_extraction.extract_event_fields_llm", spy)

    call_command("eval_extraction", "--limit", "2")

    assert len(calls) == 2
