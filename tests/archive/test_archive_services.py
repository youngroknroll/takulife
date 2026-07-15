"""Archive service-layer tests — direct service calls, no HTTP."""
import pytest
from django.core.exceptions import ValidationError
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


@pytest.mark.django_db
def test_create_personal_entry_rejects_goods_kind(make_user):
    """GOODS is no longer creatable via PersonalEntry (collection domain plan
    §3-3) — goods live in the dedicated CollectionItem domain instead."""
    user = make_user(username="pe-service-goods")

    with pytest.raises(ValidationError):
        create_personal_entry(user=user, kind="goods", title="차단되어야 할 굿즈")


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


@pytest.mark.django_db
def test_create_collection_item_rejects_negative_quantity_before_db(make_user):
    user = make_user(username="ci-service-neg-qty")

    with pytest.raises(ValidationError):
        create_collection_item(user=user, name="음수 수량", quantity=-1)


@pytest.mark.django_db
def test_create_collection_item_rejects_negative_tradeable_quantity_before_db(make_user):
    user = make_user(username="ci-service-neg-tradeable")

    with pytest.raises(ValidationError):
        create_collection_item(
            user=user, name="음수 교환 수량", quantity=5, tradeable_quantity=-1
        )


@pytest.mark.django_db
def test_create_collection_item_rejects_tradeable_exceeding_quantity_before_db(make_user):
    user = make_user(username="ci-service-tradeable-exceeds")

    with pytest.raises(ValidationError):
        create_collection_item(
            user=user, name="초과 교환 수량", quantity=1, tradeable_quantity=2
        )


@pytest.mark.django_db
def test_create_collection_item_rejects_visit_record_owned_by_another_user(
    make_user, make_event, make_visit
):
    owner = make_user(username="ci-service-visit-owner")
    other = make_user(username="ci-service-other-user")
    event = make_event(title="타인 방문 이벤트")
    visit_record = make_visit(owner, event=event, visited_on="2026-01-01")

    with pytest.raises(ValidationError):
        create_collection_item(user=other, name="타인 소유 위반", visit_record=visit_record)


@pytest.mark.django_db
def test_create_collection_item_syncs_none_event_from_unofficial_visit_record(
    make_user, make_entry, make_visit, make_event
):
    user = make_user(username="ci-service-unofficial-visit")
    personal_entry = make_entry(user)
    visit_record = make_visit(user, personal_entry=personal_entry, visited_on="2026-01-01")
    conflicting_event = make_event(title="무시되어야 할 이벤트")

    item = create_collection_item(
        user=user,
        name="비공식 방문 굿즈",
        visit_record=visit_record,
        event=conflicting_event,
    )

    assert item.event_id is None


@pytest.mark.django_db
def test_create_collection_item_defaults_visibility_to_private(make_user):
    user = make_user(username="ci-service-visibility-default")

    item = create_collection_item(user=user, name="기본 공개범위 확인")

    assert item.visibility == "private"
