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
