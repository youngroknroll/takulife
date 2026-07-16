"""Archive service-layer analytics event recording
(PR-0e checkpoints B5, B6, B7).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import UserEventStatus
from archive.services import (
    create_collection_item,
    create_event_interest,
    create_user_event_status,
    create_visit_record,
    create_visit_record_photo,
    mark_visited,
    update_collection_item,
)
from core.models import AnalyticsEvent


@pytest.mark.django_db
def test_create_event_interest_records_event_interested(make_user, make_event):
    user = make_user()
    event = make_event()

    create_event_interest(user=user, event=event)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_INTERESTED
    ).count() == 1


@pytest.mark.django_db
def test_create_user_event_status_planned_records_event_planned(make_user, make_event):
    user = make_user()
    event = make_event()

    create_user_event_status(user=user, event=event, status=UserEventStatus.Status.PLANNED)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_PLANNED
    ).count() == 1


@pytest.mark.django_db
def test_create_user_event_status_visited_records_event_marked_visited(make_user, make_event):
    user = make_user()
    event = make_event()

    create_user_event_status(user=user, event=event, status=UserEventStatus.Status.VISITED)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_MARKED_VISITED
    ).count() == 1


@pytest.mark.django_db
def test_mark_visited_transition_records_event_marked_visited(make_user, make_event, make_status):
    user = make_user()
    event = make_event()
    status = make_status(user, event, status=UserEventStatus.Status.PLANNED)

    mark_visited(user_event_status=status)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.EVENT_MARKED_VISITED
    ).count() == 1


@pytest.mark.django_db
def test_create_visit_record_records_visit_record_created_without_short_review(
    make_user, make_event
):
    user = make_user()
    event = make_event()

    create_visit_record(
        user=user, event=event, visited_on="2026-05-26", short_review="private notes"
    )

    events = AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.VISIT_RECORD_CREATED
    )
    assert events.count() == 1
    assert "short_review" not in events.get().context


@pytest.mark.django_db
def test_create_visit_record_photo_records_visit_photo_added(
    make_user, make_event, make_visit, png_bytes
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.VISIT_PHOTO_ADDED
    ).count() == 1


@pytest.mark.django_db
def test_create_collection_item_records_collection_item_created(make_user):
    user = make_user()

    item = create_collection_item(user=user, name="아크릴 스탠드")

    events = AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_CREATED
    )
    assert events.count() == 1
    assert events.get().target_type == "collection_item"
    assert events.get().target_id == item.id
    assert events.get().context == {}


@pytest.mark.django_db
def test_update_collection_item_records_collection_item_updated(make_user, make_collection_item):
    user = make_user()
    item = make_collection_item(user)

    update_collection_item(item=item, memo="새 메모")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_UPDATED
    ).count() == 1


@pytest.mark.django_db
def test_create_collection_item_with_visit_record_records_linked_to_visit(
    make_user, make_event, make_visit
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    create_collection_item(user=user, name="아크릴 스탠드", visit_record=record)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 1


@pytest.mark.django_db
def test_update_collection_item_new_visit_record_records_linked_to_visit(
    make_user, make_collection_item, make_event, make_visit
):
    user = make_user()
    item = make_collection_item(user)  # visit_record=None default
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    update_collection_item(item=item, visit_record=record)

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 1


@pytest.mark.django_db
def test_update_collection_item_unrelated_field_does_not_record_linked_to_visit(
    make_user, make_event, make_visit, make_collection_item
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    item = make_collection_item(user, visit_record=record, event=event)  # already linked

    update_collection_item(item=item, memo="무관한 수정")

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 0


@pytest.mark.django_db
def test_update_collection_item_resend_same_visit_record_does_not_record_linked_to_visit(
    make_user, make_event, make_visit, make_collection_item
):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    item = make_collection_item(user, visit_record=record, event=event)  # already linked

    update_collection_item(item=item, visit_record=record)  # explicit resend of same value

    assert AnalyticsEvent.objects.filter(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT
    ).count() == 0
