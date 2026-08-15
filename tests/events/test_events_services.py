import datetime

import pytest
from django.utils import timezone

from events.models import Event
from events.services import (
    DuplicateOfficialUrlError,
    InvalidEventPeriodError,
    MissingOfficialUrlError,
    PublishEventError,
    PublishEventTitleError,
    create_published_event,
    hard_delete_event,
    mark_event_verified,
    republish_event,
    unpublish_event,
    update_published_event,
)

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_공식_url이_None이면_행사_게시를_거부한다():
    with pytest.raises(MissingOfficialUrlError):
        create_published_event(title="Event", official_url=None)


@pytest.mark.django_db
def test_공식_url이_공백이면_행사_게시를_거부한다():
    with pytest.raises(MissingOfficialUrlError):
        create_published_event(title="Event", official_url="   ")


@pytest.mark.django_db
def test_공식_url을_제공하면_게시_상태로_행사를_생성한다():
    event = create_published_event(title="Event", official_url="https://example.com/event")

    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.official_url == "https://example.com/event"


@pytest.mark.django_db
def test_이미_사용중인_공식_url로_생성하면_중복_오류가_발생한다(make_event):
    make_event(
        title="Existing event",
        official_url="https://example.com/event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    with pytest.raises(DuplicateOfficialUrlError):
        create_published_event(title="Duplicate", official_url="https://example.com/event")


@pytest.mark.django_db
def test_예상치_못한_오류는_PublishEventError로_변환된다(monkeypatch):
    def raise_runtime_error(**kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("events.services.Event.objects.create", raise_runtime_error)

    with pytest.raises(PublishEventError):
        create_published_event(title="Event", official_url="https://example.com/event")


@pytest.mark.django_db
def test_시작일이_종료일보다_늦으면_행사_게시를_거부한다():
    with pytest.raises(InvalidEventPeriodError):
        create_published_event(
            title="Event",
            official_url="https://example.com/inverted",
            start_date=datetime.date(2026, 8, 10),
            end_date=datetime.date(2026, 8, 1),
        )


def test_InvalidEventPeriodError는_PublishEventError의_하위_타입이다():
    assert issubclass(InvalidEventPeriodError, PublishEventError)


def test_PublishEventTitleError는_PublishEventError의_하위_타입이다():
    assert issubclass(PublishEventTitleError, PublishEventError)


@pytest.mark.django_db
def test_시작일과_종료일이_같으면_행사_게시를_허용한다():
    event = create_published_event(
        title="Event",
        official_url="https://example.com/same-day",
        start_date=datetime.date(2026, 8, 1),
        end_date=datetime.date(2026, 8, 1),
    )

    assert event.start_date == event.end_date == datetime.date(2026, 8, 1)


@pytest.mark.django_db
def test_종료일_없이_시작일만_있어도_행사_게시를_허용한다():
    event = create_published_event(
        title="Event",
        official_url="https://example.com/open-ended",
        start_date=datetime.date(2026, 8, 1),
    )

    assert event.start_date == datetime.date(2026, 8, 1)
    assert event.end_date is None


@pytest.mark.django_db
def test_제목이_빈_문자열이면_행사_게시를_거부하고_행을_생성하지_않는다():
    with pytest.raises(PublishEventTitleError):
        create_published_event(title="", official_url="https://example.com/blank-title")

    assert not Event.objects.filter(official_url="https://example.com/blank-title").exists()


@pytest.mark.django_db
def test_제목이_공백만_있으면_행사_게시를_거부하고_행을_생성하지_않는다():
    with pytest.raises(PublishEventTitleError):
        create_published_event(title="   ", official_url="https://example.com/whitespace-title")

    assert not Event.objects.filter(official_url="https://example.com/whitespace-title").exists()


@pytest.mark.django_db
def test_제목이_공식_url과_동일하면_행사_게시를_거부하고_행을_생성하지_않는다():
    with pytest.raises(PublishEventTitleError):
        create_published_event(
            title="https://example.com/matching-title",
            official_url="https://example.com/matching-title",
        )

    assert not Event.objects.filter(official_url="https://example.com/matching-title").exists()


@pytest.mark.django_db
def test_제목과_공식_url이_슬래시_유무만_다르면_행사_게시를_거부한다():
    with pytest.raises(PublishEventTitleError):
        create_published_event(
            title="https://example.com/slash-title/",
            official_url="https://example.com/slash-title",
        )
    assert not Event.objects.filter(official_url="https://example.com/slash-title").exists()

    with pytest.raises(PublishEventTitleError):
        create_published_event(
            title="https://example.com/slash-title-2",
            official_url="https://example.com/slash-title-2/",
        )
    assert not Event.objects.filter(official_url="https://example.com/slash-title-2/").exists()


@pytest.mark.django_db
def test_제목이_공식_url과_대소문자만_다르면_행사_게시를_허용한다():
    event = create_published_event(
        title="HTTPS://EXAMPLE.COM/case-title",
        official_url="https://example.com/case-title",
    )

    assert event.title == "HTTPS://EXAMPLE.COM/case-title"
    assert event.official_url == "https://example.com/case-title"


@pytest.mark.django_db
def test_행사_수정을_요청하면_전달한_필드가_모두_갱신된다():
    event = create_published_event(title="Original", official_url="https://example.com/original")

    updated = update_published_event(
        event=event,
        title="Updated title",
        category="popup_store",
        work_title="Work",
        location_name="Seoul Hall",
        region="seoul",
        start_date=datetime.date(2026, 9, 1),
        end_date=datetime.date(2026, 9, 10),
        official_url="https://example.com/original",
        source_name="Official site",
        summary="Updated summary",
    )

    updated.refresh_from_db()
    assert updated.pk == event.pk
    assert updated.title == "Updated title"
    assert updated.category == "popup_store"
    assert updated.work_title == "Work"
    assert updated.location_name == "Seoul Hall"
    assert updated.region == "seoul"
    assert updated.start_date == datetime.date(2026, 9, 1)
    assert updated.end_date == datetime.date(2026, 9, 10)
    assert updated.official_url == "https://example.com/original"
    assert updated.source_name == "Official site"
    assert updated.summary == "Updated summary"
    # publish_status는 이 서비스의 책임 범위 밖이다.
    assert updated.publish_status == Event.PublishStatus.PUBLISHED


@pytest.mark.django_db
def test_공식_url을_그대로_유지한_채_저장하면_수정을_허용한다():
    event = create_published_event(title="Event", official_url="https://example.com/self")

    updated = update_published_event(
        event=event,
        title="Event renamed",
        official_url="https://example.com/self",
    )

    assert updated.title == "Event renamed"
    assert updated.official_url == "https://example.com/self"


@pytest.mark.django_db
def test_공식_url을_공백으로_수정하면_거부하고_기존_값을_유지한다():
    event = create_published_event(title="Event", official_url="https://example.com/blank-target")

    with pytest.raises(MissingOfficialUrlError):
        update_published_event(event=event, title="Event", official_url="   ")

    event.refresh_from_db()
    assert event.official_url == "https://example.com/blank-target"


@pytest.mark.django_db
def test_제목을_공백으로_수정하면_거부하고_기존_값을_유지한다():
    event = create_published_event(title="Event", official_url="https://example.com/blank-title-target")

    with pytest.raises(PublishEventTitleError):
        update_published_event(event=event, title="   ", official_url="https://example.com/blank-title-target")

    event.refresh_from_db()
    assert event.title == "Event"


@pytest.mark.django_db
def test_수정_시_시작일이_종료일보다_늦으면_거부하고_원래_상태를_유지한다():
    event = create_published_event(title="Event", official_url="https://example.com/period-target")

    with pytest.raises(InvalidEventPeriodError):
        update_published_event(
            event=event,
            title="Event",
            official_url="https://example.com/period-target",
            start_date=datetime.date(2026, 8, 10),
            end_date=datetime.date(2026, 8, 1),
        )

    event.refresh_from_db()
    assert event.start_date is None
    assert event.end_date is None


@pytest.mark.django_db
def test_다른_행사가_사용중인_공식_url로_수정하면_거부하고_기존_값을_유지한다():
    create_published_event(title="Other event", official_url="https://example.com/taken")
    event = create_published_event(title="Event", official_url="https://example.com/mine")

    with pytest.raises(DuplicateOfficialUrlError):
        update_published_event(event=event, title="Event", official_url="https://example.com/taken")

    event.refresh_from_db()
    assert event.official_url == "https://example.com/mine"


@pytest.mark.django_db
def test_수정_중_예상치_못한_오류는_PublishEventError로_변환된다(monkeypatch):
    event = create_published_event(title="Event", official_url="https://example.com/unexpected")

    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(Event, "save", raise_runtime_error)

    with pytest.raises(PublishEventError):
        update_published_event(event=event, title="Event renamed", official_url="https://example.com/unexpected")


@pytest.mark.django_db
def test_게시_취소를_요청하면_행사가_초안_상태로_전환된다():
    event = create_published_event(title="Event", official_url="https://example.com/unpublish-me")

    unpublish_event(event=event)

    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT


@pytest.mark.django_db
def test_재게시를_요청하면_초안_행사가_다시_게시_상태로_전환된다():
    event = create_published_event(title="Event", official_url="https://example.com/republish-me")
    unpublish_event(event=event)
    event.refresh_from_db()

    republish_event(event=event)

    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.PUBLISHED


@pytest.mark.django_db
def test_제목이_공백인_초안_행사는_재게시를_거부하고_초안_상태를_유지한다():
    event = create_published_event(title="Event", official_url="https://example.com/broken-republish")
    unpublish_event(event=event)
    event.title = "   "
    event.save(update_fields=["title"])

    with pytest.raises(PublishEventTitleError):
        republish_event(event=event)

    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT


@pytest.mark.django_db
def test_공식_url이_없는_초안_행사는_재게시를_거부하고_초안_상태를_유지한다():
    event = create_published_event(title="Event", official_url="https://example.com/broken-republish-url")
    unpublish_event(event=event)
    event.official_url = ""
    event.save(update_fields=["official_url"])

    with pytest.raises(MissingOfficialUrlError):
        republish_event(event=event)

    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT


# hard_delete_event는 순수 삭제만 수행하며 archive를 알지 못한다 — 호출자가
# archive 참조가 0건임을 먼저 확인해야 한다(staff/services.py 참고).


@pytest.mark.django_db
def test_검증을_요청하면_검증_시각이_DB에_영속된다():
    event = create_published_event(title="Event", official_url="https://example.com/verify-me")

    before = timezone.now()
    mark_event_verified(event=event)
    after = timezone.now()

    # refresh_from_db()가 꼭 필요하다: 메모리상 event 인스턴스만 단언하면
    # mark_event_verified()가 save()를 호출하지 않아도 통과할 수 있다(메모리
    # 속성만 바뀌고 DB에는 반영되지 않은 채로). DB에서 다시 읽어야 실제
    # 영속화를 증명한다. 이 재조회는 지우지 마라.
    event.refresh_from_db()

    assert event.verified_at is not None
    assert before <= event.verified_at <= after


@pytest.mark.django_db
def test_영구_삭제를_요청하면_행사_행이_삭제된다():
    event = create_published_event(title="Event", official_url="https://example.com/delete-me")
    pk = event.pk

    hard_delete_event(event=event)

    assert not Event.objects.filter(pk=pk).exists()
