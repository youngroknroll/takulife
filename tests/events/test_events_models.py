"""Event model tests — field defaults and dunder behavior, no HTTP
(moved from tests/core/test_coverage_supplements.py)."""
import pytest

from events.models import Event

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_행사를_문자열로_표현하면_제목이_된다():
    assert str(Event(title="행사 제목")) == "행사 제목"


@pytest.mark.django_db
def test_모델_기본값으로_생성한_행사의_게시_상태는_초안이다():
    """The model's own field default, not make_event's PUBLISHED override —
    make_event injects publish_status=PUBLISHED for test convenience, which
    would silently hide a regression in the model's actual default. Created
    directly via Event.objects.create, bypassing that fixture."""
    event = Event.objects.create(title="기본값 확인용")

    assert event.publish_status == Event.PublishStatus.DRAFT
