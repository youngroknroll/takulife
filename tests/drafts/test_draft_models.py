"""Tests for EventDraft field-level behavior — extraction_method/confidence
(added for LLM prefill, PR-B). Kept in a dedicated file: no existing
drafts-model-focused test module owns EventDraft field defaults/validation.
"""
import pytest
from django.core.exceptions import ValidationError

from drafts.models import EventDraft

pytestmark = pytest.mark.domain


@pytest.mark.django_db
class TestExtractionMethodField:
    def test_extraction_method를_지정하지_않으면_기본값_heuristic으로_저장된다(self, make_draft):
        draft = make_draft("https://example.com/event")

        assert draft.extraction_method == EventDraft.ExtractionMethod.HEURISTIC

    def test_extraction_method에_llm_값을_저장하면_그대로_유지된다(self, make_draft):
        draft = make_draft("https://example.com/event", extraction_method=EventDraft.ExtractionMethod.LLM)
        draft.refresh_from_db()

        assert draft.extraction_method == EventDraft.ExtractionMethod.LLM

    def test_extraction_method에_허용되지_않은_값을_지정하면_full_clean에서_검증_오류가_난다(self):
        draft = EventDraft(
            source_url="https://example.com/event",
            extraction_method="not-a-real-method",
        )

        with pytest.raises(ValidationError):
            draft.full_clean()


@pytest.mark.django_db
class TestConfidenceField:
    def test_confidence를_지정하지_않으면_기본값_None으로_저장된다(self, make_draft):
        draft = make_draft("https://example.com/event")

        assert draft.confidence is None

    def test_confidence에_실수_값을_저장하면_그대로_유지된다(self, make_draft):
        draft = make_draft("https://example.com/event", confidence=0.87)
        draft.refresh_from_db()

        assert draft.confidence == pytest.approx(0.87)


# ---------------------------------------------------------------------------
# __str__ (moved from tests/core/test_coverage_supplements.py)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_이벤트_드래프트를_문자열로_표현하면_출처_url이_된다():
    draft = EventDraft(source_url="https://example.com/x")
    assert str(draft) == "https://example.com/x"
