"""Behavior tests for the EventInterest API endpoints.

Endpoint coverage:
  POST   /api/event-interests/         → 201 or 409
  GET    /api/event-interests/         → paginated list (user-scoped)
  GET    /api/event-interests/<id>/    → 200 or 404
  DELETE /api/event-interests/<id>/    → 204 or 404
"""

import pytest

from archive.models import EventInterest


# ---------------------------------------------------------------------------
# CREATE — 201
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_event_interest_returns_201(client, make_user, make_event):
    user = make_user(username="interest-create-user")
    event = make_event(title="Popup Store A")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["event"] == event.id
    assert "id" in data
    assert EventInterest.objects.filter(user=user, event=event).exists()


# ---------------------------------------------------------------------------
# CREATE — duplicate → 409
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_event_interest_duplicate_returns_409(client, make_user, make_event):
    user = make_user(username="interest-dup-user")
    event = make_event(title="Popup Store B")

    client.force_login(user)
    client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "duplicate_event_interest",
        "detail": "Event interest already exists for this event.",
    }


# ---------------------------------------------------------------------------
# CREATE — unpublished event → 400
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_event_interest_rejects_unpublished_event(client, make_user, make_draft_event):
    user = make_user(username="interest-draft-user")
    event = make_draft_event(title="Draft Popup")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "event" in response.json()


# ---------------------------------------------------------------------------
# LIST — user-scoped
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_interest_list_is_user_scoped(client, make_user, make_event, make_interest):
    user = make_user(username="interest-list-user")
    other = make_user(username="interest-list-other")
    event_a = make_event(title="Event A")
    event_b = make_event(title="Event B")

    make_interest(user, event=event_a)
    make_interest(other, event=event_b)

    client.force_login(user)
    response = client.get("/api/event-interests/")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"count", "next", "previous", "results"}
    assert payload["count"] == 1
    assert payload["results"][0]["event"] == event_a.id


# ---------------------------------------------------------------------------
# LIST — newest-first ordering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_interest_list_ordered_newest_first(client, make_user, make_event, make_interest):
    user = make_user(username="interest-order-user")
    event_a = make_event(title="Event Order A")
    event_b = make_event(title="Event Order B")

    first_interest = make_interest(user, event=event_a)
    second_interest = make_interest(user, event=event_b)

    client.force_login(user)
    response = client.get("/api/event-interests/")

    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["id"] == second_interest.id
    assert results[1]["id"] == first_interest.id


# ---------------------------------------------------------------------------
# DELETE — 204 then 404
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_delete_event_interest_returns_204_then_404(client, make_user, make_event):
    user = make_user(username="interest-delete-user")
    event = make_event(title="Popup Delete")

    client.force_login(user)
    create_response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )
    interest_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/event-interests/{interest_id}/")
    assert delete_response.status_code == 204
    assert not EventInterest.objects.filter(pk=interest_id).exists()

    get_response = client.get(f"/api/event-interests/{interest_id}/")
    assert get_response.status_code == 404


# ---------------------------------------------------------------------------
# IDOR — cross-user delete → 404 + row survives
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cross_user_delete_returns_404_and_row_survives(client, make_user, make_event, make_interest):
    owner = make_user(username="interest-owner")
    attacker = make_user(username="interest-attacker")
    event = make_event(title="Popup IDOR")

    interest = make_interest(owner, event=event)

    client.force_login(attacker)
    response = client.delete(f"/api/event-interests/{interest.pk}/")

    assert response.status_code == 404
    assert EventInterest.objects.filter(pk=interest.pk).exists()


# ---------------------------------------------------------------------------
# Coexistence — interest + planned on same event
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_interest_and_planned_status_coexist_on_same_event(client, make_user, make_event):
    """A user can hold both an EventInterest and a planned UserEventStatus
    for the same event simultaneously. Both must be independently retrievable."""
    from archive.models import UserEventStatus

    user = make_user(username="interest-coexist-user")
    event = make_event(title="Popup Coexist")

    client.force_login(user)

    interest_response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )
    assert interest_response.status_code == 201
    interest_id = interest_response.json()["id"]

    status_response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    assert status_response.status_code == 201
    status_id = status_response.json()["id"]

    assert EventInterest.objects.filter(pk=interest_id, user=user).exists()
    assert UserEventStatus.objects.filter(pk=status_id, user=user, status="planned").exists()

    get_interest = client.get(f"/api/event-interests/{interest_id}/")
    assert get_interest.status_code == 200

    get_status = client.get(f"/api/user-event-statuses/{status_id}/")
    assert get_status.status_code == 200


# ---------------------------------------------------------------------------
# Unauthenticated → 403
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unauthenticated_cannot_create_event_interest(client, make_event):
    event = make_event(title="Popup Unauth")

    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_unauthenticated_cannot_list_event_interests(client):
    response = client.get("/api/event-interests/")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# archive_interests page view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_archive_interests_page_renders_200(client, make_user, make_event, make_interest):
    user = make_user(username="interests-page-user")
    event = make_event(title="Page Event")
    make_interest(user, event=event)

    client.force_login(user)
    response = client.get("/archive/interests/")

    assert response.status_code == 200
    assert str(event.id).encode() in response.content


@pytest.mark.django_db
def test_archive_interests_page_unauthenticated_redirects(client):
    response = client.get("/archive/interests/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
