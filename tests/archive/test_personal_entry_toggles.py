"""Phase 3 UI: the 비공식 page (/archive/items/) exposes 찜 and 방문예정 toggles per
card so a user can mark an unofficial item, with kind-aware labels (goods → 구매…).
View-level assertions on the rendered toggle state.
"""
import pytest

from archive.models import PersonalEntry


@pytest.mark.django_db
def test_items_page_hides_toggles_for_goods(client, make_user, make_entry):
    # GOODS is no longer a valid interest/status subject (collection domain
    # plan §3-3) — its row must render with no toggle markup at all, even for
    # a legacy row created before the write path was closed.
    user = make_user(username="toggles-goods-hidden")
    make_entry(user, kind="goods", title="아크릴 스탠드")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert "data-interest-toggle" not in body
    assert "data-status-action" not in body


@pytest.mark.django_db
def test_items_page_reflects_existing_interest(client, make_user, make_interest, make_entry):
    user = make_user(username="toggles-fav")
    entry = make_entry(user, kind="place", title="비공식 카페")
    interest = make_interest(user, personal_entry=entry)
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert f'data-interest-id="{interest.id}"' in body
    assert "♥" in body


@pytest.mark.django_db
def test_items_page_hides_existing_planned_status_for_goods(client, make_user, make_status, make_entry):
    # A goods row that already has a status (transitional data from before the
    # gate existed) must not render its status-id markup — the whole
    # interest/status action area is hidden for goods (collection domain plan
    # §3-3).
    user = make_user(username="toggles-goods-planned")
    entry = make_entry(user, kind="goods", title="굿즈")
    status = make_status(user, personal_entry=entry, status="planned")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert f'data-status-id="{status.id}"' not in body


@pytest.mark.django_db
def test_place_entry_uses_visit_wording(client, make_user, make_entry):
    user = make_user(username="toggles-place")
    make_entry(user, kind="place", title="숨은 카페")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert "방문 예정" in body


@pytest.mark.django_db
def test_items_page_shows_promote_button_when_not_submitted(client, make_user, make_entry):
    user = make_user(username="promote-ui-new")
    entry = make_entry(user, kind="place", title="비공식")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert f'data-promote-toggle="{entry.id}"' in body
    assert "검수 중" not in body


@pytest.mark.django_db
def test_items_page_shows_review_badge_when_submitted(client, make_user, make_entry):
    user = make_user(username="promote-ui-done")
    entry = make_entry(user, kind="place", title="비공식", promotion_status=PersonalEntry.PromotionStatus.SUBMITTED)
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert "검수 중" in body
    assert f'data-promote-toggle="{entry.id}"' not in body
