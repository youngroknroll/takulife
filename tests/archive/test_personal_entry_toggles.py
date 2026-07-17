"""Phase 3 UI: the 비공식 page (/archive/items/) exposes 찜 and 방문예정 toggles per
card so a user can mark an unofficial item, with kind-aware labels (goods → 구매…).
View-level assertions on the rendered toggle state.
"""
import pytest

from archive.models import PersonalEntry

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_굿즈_항목은_목록에서_찜과_방문예정_토글이_숨겨진다(client, make_user, make_entry):
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
def test_기존_찜이_있으면_목록에_찜_표시가_반영된다(client, make_user, make_interest, make_entry):
    user = make_user(username="toggles-fav")
    entry = make_entry(user, kind="place", title="비공식 카페")
    interest = make_interest(user, personal_entry=entry)
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert f'data-interest-id="{interest.id}"' in body
    assert "♥" in body


@pytest.mark.django_db
def test_굿즈_항목에_기존_참석예정_상태가_있어도_목록에서_숨겨진다(client, make_user, make_status, make_entry):
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
def test_장소_항목은_방문_예정_문구를_사용한다(client, make_user, make_entry):
    user = make_user(username="toggles-place")
    make_entry(user, kind="place", title="숨은 카페")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert "방문 예정" in body


@pytest.mark.django_db
def test_검수_미제출_항목은_목록에_공식_제보_버튼이_노출된다(client, make_user, make_entry):
    user = make_user(username="promote-ui-new")
    entry = make_entry(user, kind="place", title="비공식")
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert f'data-promote-toggle="{entry.id}"' in body
    assert "검수 중" not in body


@pytest.mark.django_db
def test_검수_제출된_항목은_목록에_검수_중_배지가_노출되고_제보_버튼은_숨겨진다(client, make_user, make_entry):
    user = make_user(username="promote-ui-done")
    entry = make_entry(user, kind="place", title="비공식", promotion_status=PersonalEntry.PromotionStatus.SUBMITTED)
    client.force_login(user)

    body = client.get("/archive/items/").content.decode()

    assert "검수 중" in body
    assert f'data-promote-toggle="{entry.id}"' not in body
