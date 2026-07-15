"""Tests for the CollectionItem API — user-owned goods collection items,
owner-scoped (collection domain design plan §4 PR-C5).

  POST   /api/collection-items/        → 201 (owner = request.user, never
                                          the payload)
  GET    /api/collection-items/        → paginated list (user-scoped,
                                          filterable)
  GET    /api/collection-items/<id>/   → 200 or 404
  PATCH  /api/collection-items/<id>/   → 200 or 404 (guarded update)
  DELETE /api/collection-items/<id>/   → 204 or 404
"""
import pytest

from archive.models import CollectionItem


# ---------------------------------------------------------------------------
# CP1: authentication required
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_collection_item_list_requires_authentication(client):
    response = client.get("/api/collection-items/")

    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# CP2: create — owner forced from request, never the payload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_collection_item_returns_201_and_forces_owner_from_request(client, make_user):
    user = make_user(username="ci-create-owner")
    other = make_user(username="ci-create-payload-user")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"user": other.id, "name": "새 굿즈"},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "새 굿즈"
    item = CollectionItem.objects.get(id=data["id"])
    assert item.user_id == user.id  # payload's "user" is ignored


# ---------------------------------------------------------------------------
# CP3: visibility is fully excluded (write and read) — reserved for the
# future trade opt-in gate, no exposure until Stage 4 (AGENTS.md Binding
# Product Decisions: exchange visibility requires explicit, independently
# revocable opt-in — not approved yet).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_collection_item_response_has_exact_field_set(client, make_user):
    user = make_user(username="ci-create-fields")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"name": "필드 확인용 굿즈"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert set(response.json()) == {
        "id",
        "name",
        "work_title",
        "character_name",
        "item_type",
        "quantity",
        "acquired_on",
        "acquisition_source",
        "event",
        "visit_record",
        "image",
        "memo",
        "is_wanted",
        "tradeable_quantity",
        "created_at",
        "updated_at",
    }


# ---------------------------------------------------------------------------
# CP12: a domain ValidationError raised by create_collection_item's quantity
# guard must surface as a 400, not an unhandled 500 — DRF's default
# exception handler does not translate django.core.exceptions.ValidationError
# on its own.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_collection_item_rejects_negative_quantity_with_400(client, make_user):
    user = make_user(username="ci-create-negative-quantity")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"name": "음수 수량", "quantity": -1},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "quantity" in response.json()
    assert not CollectionItem.objects.filter(name="음수 수량").exists()


# ---------------------------------------------------------------------------
# CP4~CP6: owner scoping across list, detail (GET/PATCH/DELETE)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_collection_item_list_is_user_scoped(client, make_user, make_collection_item):
    user = make_user(username="ci-list-scope")
    other = make_user(username="ci-list-scope-other")
    make_collection_item(user, name="Mine")
    make_collection_item(other, name="Theirs")

    client.force_login(user)
    response = client.get("/api/collection-items/")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["Mine"]


@pytest.mark.django_db
def test_collection_item_detail_get_for_another_user_returns_404(
    client, make_user, make_collection_item
):
    owner = make_user(username="ci-detail-get-owner")
    other = make_user(username="ci-detail-get-other")
    item = make_collection_item(owner, name="타인 소유")

    client.force_login(other)
    response = client.get(f"/api/collection-items/{item.id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_collection_item_detail_patch_for_another_user_returns_404(
    client, make_user, make_collection_item
):
    owner = make_user(username="ci-detail-patch-owner")
    other = make_user(username="ci-detail-patch-other")
    item = make_collection_item(owner, name="타인 소유 수정 시도")

    client.force_login(other)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"name": "가로채기"},
        content_type="application/json",
    )

    assert response.status_code == 404
    item.refresh_from_db()
    assert item.name == "타인 소유 수정 시도"


@pytest.mark.django_db
def test_collection_item_detail_delete_for_another_user_returns_404(
    client, make_user, make_collection_item
):
    owner = make_user(username="ci-detail-delete-owner")
    other = make_user(username="ci-detail-delete-other")
    item = make_collection_item(owner, name="타인 소유 삭제 시도")

    client.force_login(other)
    response = client.delete(f"/api/collection-items/{item.id}/")

    assert response.status_code == 404
    assert CollectionItem.objects.filter(id=item.id).exists()


@pytest.mark.django_db
def test_collection_item_owner_can_delete(client, make_user, make_collection_item):
    user = make_user(username="ci-delete-owner")
    item = make_collection_item(user, name="삭제할 항목")

    client.force_login(user)
    response = client.delete(f"/api/collection-items/{item.id}/")

    assert response.status_code == 204
    assert not CollectionItem.objects.filter(id=item.id).exists()


# ---------------------------------------------------------------------------
# CP13: PATCH routes through update_collection_item (the guarded service),
# not a raw ModelSerializer save.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_patch_collection_item_fields(client, make_user, make_collection_item):
    user = make_user(username="ci-patch-owner")
    item = make_collection_item(user, name="원래 이름")

    client.force_login(user)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"name": "바뀐 이름", "memo": "메모 추가"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["name"] == "바뀐 이름"
    item.refresh_from_db()
    assert item.name == "바뀐 이름"
    assert item.memo == "메모 추가"


@pytest.mark.django_db
def test_create_collection_item_rejects_unpublished_event(client, make_user, make_event):
    """`event` is scoped to Event.objects.published() on the serializer, the
    same guard VisitRecordSerializer/UserEventStatusSerializer already use
    (collection domain design plan §4 PR-C5 CP14)."""
    from events.models import Event

    user = make_user(username="ci-create-unpublished-event")
    draft_event = make_event(title="미공개 이벤트", publish_status=Event.PublishStatus.DRAFT)

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"name": "미공개 이벤트 굿즈", "event": draft_event.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "event" in response.json()
    assert not CollectionItem.objects.filter(name="미공개 이벤트 굿즈").exists()


@pytest.mark.django_db
def test_create_collection_item_rejects_another_users_visit_record(
    client, make_user, make_event, make_visit
):
    """API-level rejection of another user's visit_record — enforced by
    create_collection_item's service-level ownership guard, not a serializer
    queryset restriction (collection domain design plan §4 PR-C5 CP15)."""
    user = make_user(username="ci-create-cross-user-visit")
    other = make_user(username="ci-create-cross-user-visit-owner")
    event = make_event(title="타인 방문 이벤트")
    other_visit = make_visit(other, event=event, visited_on="2026-01-01")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"name": "타인 방문 굿즈", "visit_record": other_visit.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not CollectionItem.objects.filter(name="타인 방문 굿즈").exists()


@pytest.mark.django_db
def test_patch_rejects_quantity_below_existing_tradeable_quantity(
    client, make_user, make_collection_item
):
    """A PATCH that only sends `quantity` must still be checked against the
    row's existing `tradeable_quantity` — proves the PATCH path runs through
    update_collection_item's merged-value guard, not a raw serializer save
    (collection domain design plan §5 acceptance criterion 3)."""
    user = make_user(username="ci-patch-merge-guard")
    item = make_collection_item(user, name="병합 가드", quantity=5, tradeable_quantity=3)

    client.force_login(user)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"quantity": 1},
        content_type="application/json",
    )

    assert response.status_code == 400
    item.refresh_from_db()
    assert item.quantity == 5
