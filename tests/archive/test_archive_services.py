"""Archive service-layer tests — direct service calls, no HTTP."""
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from archive.models import CollectionItem, VisitRecord
from archive.services import (
    DuplicateUserEventStatusError,
    PhotoLimitExceededError,
    create_collection_item,
    create_personal_entry,
    create_user_event_status,
    create_visit_record_photo,
    update_collection_item,
)
from events.models import Event


@pytest.mark.domain
@pytest.mark.django_db
def test_이벤트를_대상으로_상태를_생성하면_사용자와_이벤트와_상태값이_그대로_저장된다(make_user, make_event):
    user = make_user(email="service-user@example.com", username="service-user")
    event = make_event(
        title="Published event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    created = create_user_event_status(user=user, event=event, status="planned")

    assert created.user_id == user.id
    assert created.event_id == event.id
    assert created.status == "planned"


@pytest.mark.domain
@pytest.mark.django_db
def test_DB_무결성_오류가_발생하면_상태_생성은_중복_예외로_변환된다(monkeypatch, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("archive.services.UserEventStatus.objects.create", raise_integrity_error)

    with pytest.raises(DuplicateUserEventStatusError):
        create_user_event_status(user=user, event=event, status="planned")


@pytest.mark.contract
@pytest.mark.django_db
def test_방문기록_사진을_추가하면_동시_업로드_방지를_위해_부모_방문기록_행을_잠근다(make_user, make_event, png_bytes, settings, tmp_path, monkeypatch, make_visit):
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


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록_사진이_상한에_도달하면_추가_업로드는_예외로_거부된다(make_user, make_event, png_bytes, settings, tmp_path, make_visit, make_visit_photo):
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


@pytest.mark.domain
@pytest.mark.django_db
def test_비공식_항목을_생성하면_입력한_필드가_그대로_저장된다(make_user):
    user = make_user(username="pe-service")
    entry = create_personal_entry(
        user=user, kind="place", title="비공식 팝업", location_name="성수"
    )

    assert entry.pk is not None
    assert entry.user == user
    assert entry.location_name == "성수"


@pytest.mark.domain
@pytest.mark.django_db
def test_굿즈_kind로_비공식_항목_생성을_시도하면_거부된다(make_user):
    """GOODS is no longer creatable via PersonalEntry (collection domain plan
    §3-3) — goods live in the dedicated CollectionItem domain instead."""
    user = make_user(username="pe-service-goods")

    with pytest.raises(ValidationError):
        create_personal_entry(user=user, kind="goods", title="차단되어야 할 굿즈")


# ---------------------------------------------------------------------------
# create_collection_item (PR-C1)
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록을_연결해_컬렉션_아이템을_생성하면_이벤트가_방문기록의_이벤트로_자동_동기화된다(make_user, make_event, make_visit):
    user = make_user(username="ci-service-sync")
    event = make_event(title="싱크할 이벤트")
    visit_record = make_visit(user, event=event, visited_on="2026-01-01")

    item = create_collection_item(
        user=user, name="이벤트 한정 굿즈", visit_record=visit_record
    )

    assert item.visit_record_id == visit_record.id
    assert item.event_id == event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록과_충돌하는_이벤트를_함께_지정해_생성해도_방문기록의_이벤트가_우선한다(
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


@pytest.mark.domain
@pytest.mark.django_db
def test_수량이_음수인_컬렉션_아이템_생성은_DB_저장_전에_거부된다(make_user):
    user = make_user(username="ci-service-neg-qty")

    with pytest.raises(ValidationError) as exc_info:
        create_collection_item(user=user, name="음수 수량", quantity=-1)

    # A negative quantity also numerically exceeds the default
    # tradeable_quantity (0), so the tradeable_quantity>quantity elif also
    # fires alongside this branch — check only the quantity key's message,
    # not the full dict, so this test stays scoped to CP1's branch.
    assert exc_info.value.message_dict["quantity"] == ["quantity는 0 이상이어야 합니다."]


@pytest.mark.domain
@pytest.mark.django_db
def test_교환가능_수량이_음수인_컬렉션_아이템_생성은_DB_저장_전에_거부된다(make_user):
    user = make_user(username="ci-service-neg-tradeable")

    with pytest.raises(ValidationError) as exc_info:
        create_collection_item(
            user=user, name="음수 교환 수량", quantity=5, tradeable_quantity=-1
        )

    assert exc_info.value.message_dict == {
        "tradeable_quantity": ["tradeable_quantity는 0 이상이어야 합니다."]
    }


@pytest.mark.domain
@pytest.mark.django_db
def test_교환가능_수량이_보유_수량을_초과하는_생성은_거부된다(make_user):
    user = make_user(username="ci-service-tradeable-exceeds")

    with pytest.raises(ValidationError) as exc_info:
        create_collection_item(
            user=user, name="초과 교환 수량", quantity=1, tradeable_quantity=2
        )

    assert exc_info.value.message_dict == {
        "tradeable_quantity": ["tradeable_quantity는 quantity 이하여야 합니다."]
    }


@pytest.mark.domain
@pytest.mark.django_db
def test_타인_소유의_방문기록을_연결해_생성을_시도하면_거부된다(
    make_user, make_event, make_visit
):
    owner = make_user(username="ci-service-visit-owner")
    other = make_user(username="ci-service-other-user")
    event = make_event(title="타인 방문 이벤트")
    visit_record = make_visit(owner, event=event, visited_on="2026-01-01")

    with pytest.raises(ValidationError) as exc_info:
        create_collection_item(user=other, name="타인 소유 위반", visit_record=visit_record)

    assert exc_info.value.message_dict == {
        "visit_record": ["visit_record는 요청한 사용자의 소유여야 합니다."]
    }


@pytest.mark.domain
@pytest.mark.django_db
def test_비공식_개인항목에_연결된_방문기록으로_생성하면_이벤트는_없음으로_동기화된다(
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


@pytest.mark.domain
@pytest.mark.django_db
def test_공개범위를_지정하지_않고_생성하면_기본값은_비공개이다(make_user):
    user = make_user(username="ci-service-visibility-default")

    item = create_collection_item(user=user, name="기본 공개범위 확인")

    assert item.visibility == "private"


# ---------------------------------------------------------------------------
# update_collection_item (PR-C5)
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_이름과_메모를_수정하면_컬렉션_아이템에_반영되어_저장된다(make_user):
    user = make_user(username="ci-update-simple")
    item = create_collection_item(user=user, name="원래 이름", memo="원래 메모")

    updated = update_collection_item(item=item, name="바뀐 이름", memo="바뀐 메모")

    item.refresh_from_db()
    assert updated.name == "바뀐 이름"
    assert item.name == "바뀐 이름"
    assert item.memo == "바뀐 메모"


@pytest.mark.domain
@pytest.mark.django_db
def test_수량만_수정해도_기존_교환가능_수량과_병합해_역전되면_거부된다(make_user):
    """A partial PATCH that only sends quantity must still be checked against
    the *existing* tradeable_quantity — omitting tradeable from the payload
    must not bypass the invariant (collection domain design plan §5
    acceptance criterion 3)."""
    user = make_user(username="ci-update-merge-guard")
    item = create_collection_item(
        user=user, name="병합 가드", quantity=5, tradeable_quantity=3
    )

    with pytest.raises(ValidationError):
        update_collection_item(item=item, quantity=1)

    item.refresh_from_db()
    assert item.quantity == 5


@pytest.mark.domain
@pytest.mark.django_db
def test_수량을_음수로_수정하면_기존값과_병합한_뒤에도_거부된다(make_user):
    """update_collection_item's quantity<0 branch had no dedicated coverage
    before this PR — CP1 only covered create_collection_item's mirror
    check."""
    user = make_user(username="ci-update-neg-qty")
    item = create_collection_item(user=user, name="음수 수량 수정")

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, quantity=-1)

    # Same cross-firing as the create-path test above: a negative merged
    # quantity also numerically exceeds the item's existing tradeable_quantity
    # (0), so check only the quantity key's message.
    assert exc_info.value.message_dict["quantity"] == ["quantity는 0 이상이어야 합니다."]
    item.refresh_from_db()
    assert item.quantity == 1


@pytest.mark.domain
@pytest.mark.django_db
def test_교환가능_수량을_음수로_수정하면_거부된다(make_user):
    """update_collection_item's tradeable_quantity<0 branch had no dedicated
    coverage before this PR — CP2 only covered create_collection_item's
    mirror check."""
    user = make_user(username="ci-update-neg-tradeable")
    item = create_collection_item(user=user, name="음수 교환 수량 수정", quantity=5)

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, tradeable_quantity=-1)

    assert exc_info.value.message_dict == {
        "tradeable_quantity": ["tradeable_quantity는 0 이상이어야 합니다."]
    }
    item.refresh_from_db()
    assert item.tradeable_quantity == 0


@pytest.mark.domain
@pytest.mark.django_db
def test_교환가능_수량을_보유_수량보다_크게_수정하면_거부된다(make_user):
    user = make_user(username="ci-update-direct-exceed")
    item = create_collection_item(user=user, name="직접 초과", quantity=5)

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, tradeable_quantity=10)

    assert exc_info.value.message_dict == {
        "tradeable_quantity": ["tradeable_quantity는 quantity 이하여야 합니다."]
    }
    item.refresh_from_db()
    assert item.tradeable_quantity == 0


@pytest.mark.domain
@pytest.mark.django_db
def test_타인_소유의_방문기록으로_수정을_시도하면_거부된다(
    make_user, make_event, make_visit
):
    owner = make_user(username="ci-update-visit-owner")
    other = make_user(username="ci-update-other-user")
    item = create_collection_item(user=other, name="타인 소유 수정 시도")
    event = make_event(title="타인 방문 이벤트")
    visit_record = make_visit(owner, event=event, visited_on="2026-01-01")

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, visit_record=visit_record)

    assert exc_info.value.message_dict == {
        "visit_record": ["visit_record는 아이템 소유자의 소유여야 합니다."]
    }
    item.refresh_from_db()
    assert item.visit_record_id is None


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록과_충돌하는_이벤트를_함께_수정해도_방문기록의_이벤트가_우선한다(
    make_user, make_event, make_visit
):
    user = make_user(username="ci-update-override")
    visit_event = make_event(title="방문 이벤트")
    conflicting_event = make_event(title="다른 이벤트")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")
    item = create_collection_item(user=user, name="충돌 수정")

    updated = update_collection_item(
        item=item, visit_record=visit_record, event=conflicting_event
    )

    assert updated.event_id == visit_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록이_이미_연결된_아이템의_이벤트만_불일치하게_수정하면_거부된다(
    make_user, make_event, make_visit
):
    """full_clean() wiring (§6-b Deferred, collection domain design plan
    §3-1 FK-pair invariant): a row already linked to a visit_record must
    reject a PATCH that sets `event` alone to a value disagreeing with
    visit_record.event — the FK-pair invariant is not just a create-time
    guard, and CollectionItem.clean() had no caller before this."""
    user = make_user(username="ci-update-fk-pair-conflict")
    visit_event = make_event(title="고정된 방문 이벤트")
    other_event = make_event(title="불일치 이벤트")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")
    item = create_collection_item(
        user=user, name="FK 쌍 확인", visit_record=visit_record
    )

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, event=other_event)

    assert exc_info.value.message_dict == {
        "event": ["visit_record가 설정된 경우 event는 visit_record.event와 일치해야 합니다."]
    }
    item.refresh_from_db()
    assert item.event_id == visit_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록이_연결된_아이템의_이벤트를_null로_수정해도_거부된다(
    make_user, make_event, make_visit
):
    """QVL finding D1 (2026-07-16): the FK-pair guard above only fired when
    the *merged* event was non-null and mismatched — model.clean()'s own
    condition requires event_id is not None, so `PATCH {"event": None}`
    silently detached event while visit_record stayed attached, breaking
    the invariant by omission. The quantity guard already reads merged
    values (`fields.get("quantity", item.quantity)`) regardless of what the
    payload touched; this guard must apply the same discipline."""
    user = make_user(username="ci-update-fk-pair-null-event")
    visit_event = make_event(title="고정된 방문 이벤트 2")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")
    item = create_collection_item(
        user=user, name="FK 쌍 null 확인", visit_record=visit_record
    )

    with pytest.raises(ValidationError):
        update_collection_item(item=item, event=None)

    item.refresh_from_db()
    assert item.event_id == visit_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록이_없는_아이템은_이벤트를_자유롭게_수정할_수_있다(
    make_user, make_event
):
    """The FK-pair guard only applies once a visit_record is attached — a
    row with no visit_record can freely change its event link."""
    user = make_user(username="ci-update-fk-pair-free")
    new_event = make_event(title="자유롭게 연결할 이벤트")
    item = create_collection_item(user=user, name="자유 편집")

    updated = update_collection_item(item=item, event=new_event)

    assert updated.event_id == new_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_다른_요청이_먼저_커밋한_뒤에_수정하면_오래된_객체가_아니라_최신_DB_상태_기준으로_거부된다(make_user):
    """Security gate M2 (2026-07-16): simulates a race between two PATCHes
    without needing real threads. Caller B fetched its `item` object before
    caller A's write committed `tradeable_quantity=5`; B's merge check must
    be judged against the row's *current* DB state (via select_for_update),
    not B's stale Python object — otherwise B's own merge check (quantity=1
    vs its stale tradeable_quantity=0) would pass, and the resulting UPDATE
    would either violate the DB CheckConstraint (crash) or silently commit
    an inconsistent row, depending on timing. Verified by re-reading from
    the DB, not the in-memory instance, so a save() that used update_fields
    without actually persisting under a lock would not be missed."""
    user = make_user(username="ci-update-concurrent-guard")
    item = create_collection_item(
        user=user, name="동시 PATCH 경합", quantity=5, tradeable_quantity=0
    )
    stale_item = CollectionItem.objects.get(pk=item.pk)  # a second caller's fetch
    # Simulate another writer's PATCH already having committed in between.
    CollectionItem.objects.filter(pk=item.pk).update(tradeable_quantity=5)

    with pytest.raises(ValidationError):
        update_collection_item(item=stale_item, quantity=1)

    item.refresh_from_db()
    assert item.quantity == 5
    assert item.tradeable_quantity == 5


@pytest.mark.domain
@pytest.mark.django_db
def test_수정_도중_다른_요청이_먼저_삭제하면_DoesNotExist_예외가_발생한다(make_user):
    """Security gate follow-up (2026-07-16): M2's own fix — re-fetching
    under select_for_update() — introduced a new TOCTOU crash: if another
    request deletes the row between the caller's original fetch and this
    call, `CollectionItem.objects.select_for_update().get(pk=item.pk)`
    itself raises DoesNotExist. This is the service-layer half of that
    finding — archive/views.py must translate it to Http404 (see
    tests/archive/test_collection_items_api.py's
    test_patch_race_with_concurrent_delete_returns_404 for the view-layer
    half, which mirrors VisitRecordPhotoCreateView's identical
    VisitRecord.DoesNotExist -> Http404 guard for the same race shape)."""
    user = make_user(username="ci-update-concurrent-delete")
    item = create_collection_item(user=user, name="동시 삭제 경합")
    stale_item = CollectionItem.objects.get(pk=item.pk)  # a second caller's fetch
    CollectionItem.objects.filter(pk=item.pk).delete()  # concurrent delete

    with pytest.raises(CollectionItem.DoesNotExist):
        update_collection_item(item=stale_item, quantity=2)
