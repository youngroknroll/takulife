"""Tests for EventDraft field-level behavior — extraction_method/confidence
(added for LLM prefill, PR-B). Kept in a dedicated file: no existing
drafts-model-focused test module owns EventDraft field defaults/validation.
"""
import pytest
from django.core.exceptions import ValidationError

from drafts.models import EventDraft


@pytest.mark.django_db
class TestExtractionMethodField:
    def test_defaults_to_heuristic(self, make_draft):
        draft = make_draft("https://example.com/event")

        assert draft.extraction_method == EventDraft.ExtractionMethod.HEURISTIC

    def test_llm_value_round_trips(self, make_draft):
        draft = make_draft("https://example.com/event", extraction_method=EventDraft.ExtractionMethod.LLM)
        draft.refresh_from_db()

        assert draft.extraction_method == EventDraft.ExtractionMethod.LLM

    def test_invalid_choice_raises_validation_error_on_full_clean(self):
        draft = EventDraft(
            source_url="https://example.com/event",
            extraction_method="not-a-real-method",
        )

        with pytest.raises(ValidationError):
            draft.full_clean()


@pytest.mark.django_db
class TestConfidenceField:
    def test_defaults_to_none(self, make_draft):
        draft = make_draft("https://example.com/event")

        assert draft.confidence is None

    def test_float_value_round_trips(self, make_draft):
        draft = make_draft("https://example.com/event", confidence=0.87)
        draft.refresh_from_db()

        assert draft.confidence == pytest.approx(0.87)


# ---------------------------------------------------------------------------
# __str__ (moved from tests/core/test_coverage_supplements.py)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_draft_str():
    draft = EventDraft(source_url="https://example.com/x")
    assert str(draft) == "https://example.com/x"
