"""Archive model tests — field defaults and constraints, no HTTP."""
import pytest

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

