"""Archive model tests — field defaults and constraints, no HTTP."""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from archive.models import CollectionItem, PersonalEntry

pytestmark = pytest.mark.domain


# ---------------------------------------------------------------------------
# __str__ (moved from tests/core/test_coverage_supplements.py)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_개인_항목을_문자열로_표현하면_제목이_된다():
    entry = PersonalEntry(title="비공식 카페")
    assert str(entry) == "비공식 카페"


# ---------------------------------------------------------------------------
# CollectionItem (PR-C1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_컬렉션_아이템을_생성하면_소유자와_이름이_저장된다(make_user):
    user = make_user(username="ci-owner")

    item = CollectionItem.objects.create(
        user=user,
        name="아크릴 스탠드",
        quantity=1,
    )

    assert item.user_id == user.id
    assert item.name == "아크릴 스탠드"


@pytest.mark.django_db
def test_수량이_음수인_컬렉션_아이템을_생성하면_제약_위반으로_거부된다(make_user):
    user = make_user(username="ci-neg-qty")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CollectionItem.objects.create(user=user, name="위시 아이템", quantity=-1)


@pytest.mark.django_db
def test_수량이_0인_컬렉션_아이템_생성이_허용된다(make_user):
    """D1: quantity=0 represents a wanted-only (not-yet-owned) item."""
    user = make_user(username="ci-zero-qty")

    item = CollectionItem.objects.create(user=user, name="구함", quantity=0)

    assert item.quantity == 0


@pytest.mark.django_db
def test_교환_가능_수량이_보유_수량을_초과하면_제약_위반으로_거부된다(
    make_user,
):
    user = make_user(username="ci-tradeable-exceeds")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CollectionItem.objects.create(
                user=user, name="교환용", quantity=1, tradeable_quantity=2
            )


@pytest.mark.django_db
def test_교환_가능_수량이_음수이면_제약_위반으로_거부된다(make_user):
    user = make_user(username="ci-neg-tradeable")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CollectionItem.objects.create(
                user=user, name="음수 교환", quantity=5, tradeable_quantity=-1
            )


@pytest.mark.django_db
def test_방문_기록의_행사와_다른_행사를_지정하면_검증_오류가_된다(
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


@pytest.mark.django_db
def test_연결된_행사가_삭제되면_컬렉션_아이템은_행사_참조만_비운_채_유지된다(
    make_user, make_event
):
    user = make_user(username="ci-event-hard-delete")
    event = make_event(title="삭제될 이벤트")
    item = CollectionItem.objects.create(user=user, name="생존 항목", event=event)

    event.delete()
    item.refresh_from_db()

    assert item.event_id is None


@pytest.mark.django_db
def test_연결된_방문_기록이_삭제되면_컬렉션_아이템은_방문_기록_참조만_비운_채_유지된다(
    make_user, make_event, make_visit
):
    user = make_user(username="ci-visit-hard-delete")
    event = make_event(title="방문 삭제 이벤트")
    visit_record = make_visit(user, event=event, visited_on="2026-01-01")
    item = CollectionItem.objects.create(
        user=user, name="생존 항목 2", visit_record=visit_record
    )

    visit_record.delete()
    item.refresh_from_db()

    assert item.visit_record_id is None
