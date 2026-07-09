"""Event model tests — field defaults and dunder behavior, no HTTP
(moved from tests/core/test_coverage_supplements.py)."""
import pytest

from events.models import Event


@pytest.mark.django_db
def test_event_str():
    assert str(Event(title="행사 제목")) == "행사 제목"


@pytest.mark.django_db
def test_event_publish_status_defaults_to_draft():
    """The model's own field default, not make_event's PUBLISHED override —
    make_event injects publish_status=PUBLISHED for test convenience, which
    would silently hide a regression in the model's actual default. Created
    directly via Event.objects.create, bypassing that fixture."""
    event = Event.objects.create(title="기본값 확인용")

    assert event.publish_status == Event.PublishStatus.DRAFT
