"""Event 모델 테스트 — 필드 기본값, 던더 동작, 게시 여부 판정, HTTP는 다루지 않는다."""

import pytest

from events.models import Event

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_행사를_문자열로_표현하면_제목이_된다():
    assert str(Event(title="행사 제목")) == "행사 제목"


@pytest.mark.django_db
def test_모델_기본값으로_생성한_행사의_게시_상태는_초안이다():
    """make_event의 PUBLISHED 오버라이드가 아니라 모델 자체의 필드 기본값을
    검증한다 — make_event는 테스트 편의를 위해 publish_status=PUBLISHED를
    주입하므로, 모델의 실제 기본값이 회귀해도 조용히 가려질 수 있다. 그래서
    그 픽스처를 거치지 않고 Event.objects.create로 직접 생성한다."""
    event = Event.objects.create(title="기본값 확인용")

    assert event.publish_status == Event.PublishStatus.DRAFT


@pytest.mark.parametrize(
    ("publish_status", "expected"),
    [
        pytest.param(Event.PublishStatus.PUBLISHED, True, id="게시"),
        pytest.param(Event.PublishStatus.DRAFT, False, id="초안"),
    ],
)
def test_행사의_게시_여부는_게시_상태일_때만_참이다(publish_status, expected):
    event = Event(title="행사", publish_status=publish_status)

    assert event.is_published is expected


@pytest.mark.django_db
def test_행사의_게시_여부는_게시된_행사_조회와_같은_행사를_가리킨다(make_event, make_draft_event):
    make_event(title="게시 1")
    make_event(title="게시 2")
    make_draft_event(title="초안 1")
    make_draft_event(title="초안 2")

    published_by_property = {event.pk for event in Event.objects.all() if event.is_published}

    assert published_by_property == set(Event.objects.published().values_list("pk", flat=True))
