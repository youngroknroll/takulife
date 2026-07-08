"""Phase 3 UI: the 비공식 page (/archive/items/) exposes 찜 and 방문예정 toggles per
card so a user can mark an unofficial item, with kind-aware labels (goods → 구매…).
View-level assertions on the rendered toggle state.
"""
import pytest

from archive.models import EventInterest, PersonalEntry, UserEventStatus


@pytest.mark.django_db
def test_items_page_renders_inactive_toggles_for_new_goods(client, make_user):
    user = make_user(username="toggles-new")
    PersonalEntry.objects.create(user=user, kind="goods", title="아크릴 스탠드")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert "data-interest-toggle" in body
    assert "data-status-action" in body
    # goods speaks 구매, not 방문, and starts inactive (no status id yet)
    assert "구매 예정" in body
    assert "♡" in body


@pytest.mark.django_db
def test_items_page_reflects_existing_interest(client, make_user):
    user = make_user(username="toggles-fav")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 카페")
    interest = EventInterest.objects.create(user=user, personal_entry=entry)
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert f'data-interest-id="{interest.id}"' in body
    assert "♥" in body


@pytest.mark.django_db
def test_items_page_reflects_existing_planned_status(client, make_user):
    user = make_user(username="toggles-planned")
    entry = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")
    status = UserEventStatus.objects.create(
        user=user, personal_entry=entry, status="planned"
    )
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert f'data-status-id="{status.id}"' in body
    # kind-aware: a planned goods status reads 구매 예정
    assert "구매 예정" in body


@pytest.mark.django_db
def test_place_entry_uses_visit_wording(client, make_user):
    user = make_user(username="toggles-place")
    PersonalEntry.objects.create(user=user, kind="place", title="숨은 카페")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert "방문 예정" in body


@pytest.mark.django_db
def test_items_page_shows_promote_button_when_not_submitted(client, make_user):
    user = make_user(username="promote-ui-new")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert f'data-promote-toggle="{entry.id}"' in body
    assert "검수 중" not in body


@pytest.mark.django_db
def test_items_page_shows_review_badge_when_submitted(client, make_user):
    user = make_user(username="promote-ui-done")
    entry = PersonalEntry.objects.create(
        user=user,
        kind="place",
        title="비공식",
        promotion_status=PersonalEntry.PromotionStatus.SUBMITTED,
    )
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert "검수 중" in body
    assert f'data-promote-toggle="{entry.id}"' not in body
