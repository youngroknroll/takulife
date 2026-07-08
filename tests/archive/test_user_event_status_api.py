import pytest
from django.db import IntegrityError

from archive.services import DuplicateUserEventStatusError, create_user_event_status
from events.models import Event


@pytest.mark.django_db
def test_create_user_event_status_accepts_explicit_domain_inputs(django_user_model):
    user = django_user_model.objects.create_user(email="service-user@example.com", username="service-user", password="secret")
    event = Event.objects.create(
        title="Published event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    created = create_user_event_status(user=user, event=event, status="planned")

    assert created.user_id == user.id
    assert created.event_id == event.id
    assert created.status == "planned"


@pytest.mark.django_db
def test_authenticated_user_can_create_event_status_for_published_event(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id
    assert response.json()["status"] == "planned"


@pytest.mark.django_db
def test_user_event_status_create_accepts_published_event_via_events_queryset(
    client,
    django_user_model,
):
    user = django_user_model.objects.create_user(email="published-user@example.com", username="published-user", password="secret")
    event = Event.objects.create(
        title="Published event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id


@pytest.mark.django_db
def test_legacy_me_event_status_route_remains_inactive(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.put(
        f"/api/me/event-statuses/{event.id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_event_status_list_returns_only_current_users_statuses(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-owner@example.com", username="status-owner", password="secret")
    other_user = django_user_model.objects.create_user(email="status-other@example.com", username="status-other", password="secret")
    owned_event = Event.objects.create(title="Owned event", publish_status=Event.PublishStatus.PUBLISHED)
    other_event = Event.objects.create(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    client.post(
        "/api/user-event-statuses/",
        {"event": owned_event.id, "status": "planned"},
        content_type="application/json",
    )
    client.force_login(other_user)
    client.post(
        "/api/user-event-statuses/",
        {"event": other_event.id, "status": "planned"},
        content_type="application/json",
    )

    client.force_login(user)
    response = client.get("/api/user-event-statuses/")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"count", "next", "previous", "results"}
    assert payload["count"] == 1
    assert [item["event"] for item in payload["results"]] == [owned_event.id]


@pytest.mark.django_db
def test_user_event_status_list_filters_by_event_and_status(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-owner@example.com", username="status-owner", password="secret")
    event_one = Event.objects.create(title="Event one", publish_status=Event.PublishStatus.PUBLISHED)
    event_two = Event.objects.create(title="Event two", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    client.post(
        "/api/user-event-statuses/",
        {"event": event_one.id, "status": "planned"},
        content_type="application/json",
    )
    client.post(
        "/api/user-event-statuses/",
        {"event": event_two.id, "status": "planned"},
        content_type="application/json",
    )

    response = client.get(f"/api/user-event-statuses/?event={event_two.id}&status=planned")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert [item["event"] for item in payload["results"]] == [event_two.id]


@pytest.mark.django_db
def test_user_event_status_list_rejects_invalid_status_filter(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-owner@example.com", username="status-owner", password="secret")
    event = Event.objects.create(title="Event one", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    response = client.get("/api/user-event-statuses/?status=attended")

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.django_db
def test_user_event_status_detail_for_another_user_returns_404(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-owner@example.com", username="status-owner", password="secret")
    other_user = django_user_model.objects.create_user(email="status-other@example.com", username="status-other", password="secret")
    event = Event.objects.create(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(other_user)
    create_response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    status_id = create_response.json()["id"]

    client.force_login(other_user)
    own_response = client.get(f"/api/user-event-statuses/{status_id}/")

    assert own_response.status_code == 200

    client.force_login(user)
    response = client.get(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_event_status_rejects_unpublished_event(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Draft event", publish_status=Event.PublishStatus.DRAFT)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "event" in response.json()


@pytest.mark.django_db
def test_user_event_status_rejects_invalid_status(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "attended"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.django_db
def test_user_event_status_duplicate_returns_409(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "duplicate_user_event_status",
        "detail": "User event status already exists for this event.",
    }


@pytest.mark.django_db
def test_authenticated_user_can_patch_event_status(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    create_response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    status_id = create_response.json()["id"]

    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["event"] == event.id
    assert response.json()["status"] == "visited"


@pytest.mark.django_db
def test_patch_to_planned_pins_override_so_it_stays_planned(client, django_user_model):
    """Reverting an auto-missed (past planned) row to planned must stick.

    Without the override flag the read-time derivation would immediately show
    'missed' again. The PATCH must persist missed_overridden so the user's
    'keep planned' choice wins.
    """
    from datetime import date

    from archive.models import UserEventStatus

    user = django_user_model.objects.create_user(email="revert-user@example.com", username="revert-user", password="secret")
    event = Event.objects.create(
        title="Long-past event",
        publish_status=Event.PublishStatus.PUBLISHED,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),  # firmly in the past relative to any real today
    )
    client.force_login(user)
    create_response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    status_id = create_response.json()["id"]

    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 200
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "planned"
    assert row.missed_overridden is True
    # The derived view keeps it planned, not missed.
    assert (
        UserEventStatus.objects.filter(pk=status_id)
        .with_derived_status(today=date.today())
        .first()
        .derived_status
        == "planned"
    )


@pytest.mark.django_db
def test_user_event_status_put_is_not_allowed(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    other_event = Event.objects.create(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    create_response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    status_id = create_response.json()["id"]

    response = client.put(
        f"/api/user-event-statuses/{status_id}/",
        {"event": other_event.id, "status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 405
    assert client.get(f"/api/user-event-statuses/{status_id}/").json() == {
        "id": status_id,
        "event": event.id,
        "personal_entry": None,
        "status": "planned",
    }


@pytest.mark.django_db
def test_authenticated_user_can_delete_event_status(client, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    create_response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    status_id = create_response.json()["id"]

    response = client.delete(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 204
    assert client.get(f"/api/user-event-statuses/{status_id}/").status_code == 404


@pytest.mark.django_db
def test_create_user_event_status_maps_integrity_error_to_duplicate(monkeypatch, django_user_model):
    user = django_user_model.objects.create_user(email="status-user@example.com", username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("archive.services.UserEventStatus.objects.create", raise_integrity_error)

    with pytest.raises(DuplicateUserEventStatusError):
        create_user_event_status(user=user, event=event, status="planned")


@pytest.mark.django_db
def test_user_event_status_rejects_interested_as_status(client, django_user_model):
    """After removing 'interested' from UserEventStatus choices, the API must reject it."""
    user = django_user_model.objects.create_user(email="status-interested-reject@example.com", username="status-interested-reject", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "interested"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "status" in response.json()
