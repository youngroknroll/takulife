"""Archive model tests — field defaults and constraints, no HTTP."""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from archive.models import CollectionItem, PersonalEntry


@pytest.mark.django_db
def test_personal_entry_supports_place_and_goods(make_user, make_entry):
    user = make_user(username="pe-model")
    place = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="숨은 굿즈 카페")
    goods = make_entry(user, kind=PersonalEntry.Kind.GOODS, title="중고로 산 아크릴 스탠드")

    assert place.kind == "place"
    assert goods.kind == "goods"
    # optional fields default to blank, not required
    assert place.category == ""
    assert place.memo == ""


# ---------------------------------------------------------------------------
# __str__ (moved from tests/core/test_coverage_supplements.py)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_personal_entry_str():
    entry = PersonalEntry(title="비공식 카페")
    assert str(entry) == "비공식 카페"


# ---------------------------------------------------------------------------
# CollectionItem (PR-C1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_collection_item_persists_with_owner_and_name(make_user):
    user = make_user(username="ci-owner")

    item = CollectionItem.objects.create(
        user=user,
        name="아크릴 스탠드",
        quantity=1,
    )

    assert item.user_id == user.id
    assert item.name == "아크릴 스탠드"


@pytest.mark.django_db
def test_collection_item_negative_quantity_violates_check_constraint(make_user):
    user = make_user(username="ci-neg-qty")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CollectionItem.objects.create(user=user, name="위시 아이템", quantity=-1)


@pytest.mark.django_db
def test_collection_item_zero_quantity_is_allowed(make_user):
    """D1: quantity=0 represents a wanted-only (not-yet-owned) item."""
    user = make_user(username="ci-zero-qty")

    item = CollectionItem.objects.create(user=user, name="구함", quantity=0)

    assert item.quantity == 0


@pytest.mark.django_db
def test_collection_item_tradeable_quantity_exceeding_quantity_violates_check_constraint(
    make_user,
):
    user = make_user(username="ci-tradeable-exceeds")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CollectionItem.objects.create(
                user=user, name="교환용", quantity=1, tradeable_quantity=2
            )


@pytest.mark.django_db
def test_collection_item_negative_tradeable_quantity_violates_check_constraint(make_user):
    user = make_user(username="ci-neg-tradeable")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CollectionItem.objects.create(
                user=user, name="음수 교환", quantity=5, tradeable_quantity=-1
            )


@pytest.mark.django_db
def test_collection_item_clean_rejects_event_mismatched_with_visit_record(
    make_user, make_event, make_visit
):
    user = make_user(username="ci-clean-mismatch")
    visit_event = make_event(title="방문 이벤트 clean")
    mismatched_event = make_event(title="불일치 이벤트 clean")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")

    item = CollectionItem(
        user=user,
        name="불일치 항목",
        visit_record=visit_record,
        event=mismatched_event,
    )

    with pytest.raises(ValidationError):
        item.clean()
