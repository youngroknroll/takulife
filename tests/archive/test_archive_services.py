"""Archive service-layer tests — direct service calls, no HTTP."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from archive.models import VisitRecord
from archive.services import (
    DuplicateUserEventStatusError,
    PhotoLimitExceededError,
    create_collection_item,
    create_personal_entry,
    create_user_event_status,
    create_visit_record_photo,
)
from events.models import Event


@pytest.mark.django_db
def test_create_user_event_status_accepts_explicit_domain_inputs(make_user, make_event):
    user = make_user(email="service-user@example.com", username="service-user")
    event = make_event(
        title="Published event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    created = create_user_event_status(user=user, event=event, status="planned")

    assert created.user_id == user.id
    assert created.event_id == event.id
    assert created.status == "planned"


@pytest.mark.django_db
def test_create_user_event_status_maps_integrity_error_to_duplicate(monkeypatch, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("archive.services.UserEventStatus.objects.create", raise_integrity_error)

    with pytest.raises(DuplicateUserEventStatusError):
        create_user_event_status(user=user, event=event, status="planned")


@pytest.mark.django_db
def test_create_visit_record_photo_locks_the_visit_record_row(make_user, make_event, png_bytes, settings, tmp_path, monkeypatch, make_visit):
    """The count-then-create must be atomic and lock the parent VisitRecord row
    (select_for_update) so two concurrent uploads can't both pass the count
    check and push the record past MAX_PHOTOS_PER_RECORD."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    calls = []
    original_select_for_update = VisitRecord.objects.select_for_update

    def spy_select_for_update(*args, **kwargs):
        calls.append((args, kwargs))
        return original_select_for_update(*args, **kwargs)

    monkeypatch.setattr(VisitRecord.objects, "select_for_update", spy_select_for_update)

    photo = create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )

    assert photo.visit_record_id == record.id
    assert calls, "create_visit_record_photo must select_for_update the parent VisitRecord row"


@pytest.mark.django_db
def test_create_visit_record_photo_raises_when_at_cap(make_user, make_event, png_bytes, settings, tmp_path, make_visit, make_visit_photo):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    png_data = png_bytes()
    for i in range(5):
        make_visit_photo(record, filename=f"photo-{i}.png")

    with pytest.raises(PhotoLimitExceededError):
        create_visit_record_photo(
            visit_record=record,
            image=SimpleUploadedFile("extra.png", png_data, content_type="image/png"),
        )


@pytest.mark.django_db
def test_create_personal_entry_service(make_user):
    user = make_user(username="pe-service")
    entry = create_personal_entry(
        user=user, kind="place", title="비공식 팝업", location_name="성수"
    )

    assert entry.pk is not None
    assert entry.user == user
    assert entry.location_name == "성수"


# ---------------------------------------------------------------------------
# create_collection_item (PR-C1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_collection_item_syncs_event_from_visit_record(make_user, make_event, make_visit):
    user = make_user(username="ci-service-sync")
    event = make_event(title="싱크할 이벤트")
    visit_record = make_visit(user, event=event, visited_on="2026-01-01")

    item = create_collection_item(
        user=user, name="이벤트 한정 굿즈", visit_record=visit_record
    )

    assert item.visit_record_id == visit_record.id
    assert item.event_id == event.id


@pytest.mark.django_db
def test_create_collection_item_visit_record_overrides_conflicting_explicit_event(
    make_user, make_event, make_visit
):
    user = make_user(username="ci-service-override")
    visit_event = make_event(title="방문 이벤트")
    conflicting_event = make_event(title="다른 이벤트")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")

    item = create_collection_item(
        user=user,
        name="충돌 굿즈",
        visit_record=visit_record,
        event=conflicting_event,
    )

    assert item.event_id == visit_event.id
