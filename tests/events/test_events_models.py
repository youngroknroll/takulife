"""Event model tests — field defaults and dunder behavior, no HTTP
(moved from tests/core/test_coverage_supplements.py)."""
import pytest

from events.models import Event


@pytest.mark.django_db
def test_event_str():
    assert str(Event(title="행사 제목")) == "행사 제목"
