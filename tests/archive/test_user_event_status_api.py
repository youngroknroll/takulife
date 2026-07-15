from datetime import date

import pytest

from archive.models import UserEventStatus
from events.models import Event


@pytest.mark.django_db
def test_authenticated_user_can_create_event_status_for_published_event(client, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

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
def test_legacy_me_event_status_route_remains_inactive(client, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.put(
        f"/api/me/event-statuses/{event.id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_event_status_list_returns_only_current_users_statuses(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    other_user = make_user(email="status-other@example.com", username="status-other")
    owned_event = make_event(title="Owned event", publish_status=Event.PublishStatus.PUBLISHED)
    other_event = make_event(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, owned_event, status="planned")
    make_status(other_user, other_event, status="planned")

    client.force_login(user)
    response = client.get("/api/user-event-statuses/")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"count", "next", "previous", "results"}
    assert payload["count"] == 1
    assert [item["event"] for item in payload["results"]] == [owned_event.id]


@pytest.mark.django_db
def test_user_event_status_list_filters_by_event_and_status(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    event_one = make_event(title="Event one", publish_status=Event.PublishStatus.PUBLISHED)
    event_two = make_event(title="Event two", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, event_one, status="planned")
    make_status(user, event_two, status="planned")

    client.force_login(user)
    response = client.get(f"/api/user-event-statuses/?event={event_two.id}&status=planned")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert [item["event"] for item in payload["results"]] == [event_two.id]


@pytest.mark.django_db
def test_user_event_status_list_rejects_invalid_status_filter(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    event = make_event(title="Event one", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, event, status="planned")

    client.force_login(user)
    response = client.get("/api/user-event-statuses/?status=attended")

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.django_db
def test_user_event_status_detail_for_another_user_returns_404(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    other_user = make_user(email="status-other@example.com", username="status-other")
    event = make_event(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(other_user, event, status="planned")
    status_id = status.id

    client.force_login(other_user)
    own_response = client.get(f"/api/user-event-statuses/{status_id}/")

    assert own_response.status_code == 200

    client.force_login(user)
    response = client.get(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_event_status_rejects_unpublished_event(client, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Draft event", publish_status=Event.PublishStatus.DRAFT)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "event" in response.json()


@pytest.mark.django_db
def test_user_event_status_rejects_invalid_status(client, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "attended"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.django_db
def test_user_event_status_duplicate_returns_409(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, event, status="planned")

    client.force_login(user)
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
def test_authenticated_user_can_patch_event_status(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["event"] == event.id
    assert response.json()["status"] == "visited"


@pytest.mark.django_db
def test_patch_to_planned_pins_override_so_it_stays_planned(client, make_user, make_event, make_status):
    """Reverting an auto-missed (past planned) row to planned must stick.

    Without the override flag the read-time derivation would immediately show
    'missed' again. The PATCH must persist missed_overridden so the user's
    'keep planned' choice wins. (The derived-status queryset assertion for
    this same scenario lives in test_archive_missed_status.py, reconstructed
    via ORM — this test only covers the HTTP/DB-state contract of the PATCH.)
    """
    user = make_user(email="revert-user@example.com", username="revert-user")
    event = make_event(
        title="Long-past event",
        publish_status=Event.PublishStatus.PUBLISHED,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),  # firmly in the past relative to any real today
    )
    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 200
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "planned"
    assert row.missed_overridden is True


@pytest.mark.django_db
def test_user_event_status_put_is_not_allowed(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    other_event = make_event(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
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
def test_authenticated_user_can_delete_event_status(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.delete(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 204
    assert client.get(f"/api/user-event-statuses/{status_id}/").status_code == 404


@pytest.mark.django_db
def test_patch_without_status_saves_without_transition(client, make_event, make_user):
    """(moved from tests/core/test_coverage_supplements.py)"""
    user = make_user()
    event = make_event(title="상태 전환")
    status_obj = UserEventStatus.objects.create(
        user=user, event=event, status="planned"
    )

    client.force_login(user)
    # No status in the payload → validated status is None → the plain save()
    # arm (no transition) runs.
    resp = client.patch(
        f"/api/user-event-statuses/{status_obj.id}/",
        data={},
        content_type="application/json",
    )

    assert resp.status_code == 200
    status_obj.refresh_from_db()
    assert status_obj.status == "planned"


@pytest.mark.django_db
def test_user_event_status_rejects_interested_as_status(client, make_user, make_event):
    """After removing 'interested' from UserEventStatus choices, the API must reject it."""
    user = make_user(email="status-interested-reject@example.com", username="status-interested-reject")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "interested"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "status" in response.json()


# ---------------------------------------------------------------------------
# §6-b Deferred: a status-only PATCH must not recreate the drift 0016
# corrected — a subject with an existing VisitRecord can't be reverted to
# planned or marked missed via this endpoint (collection domain design plan
# §5 acceptance criterion 5).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_patch_to_planned_rejected_when_visit_record_exists(
    client, make_user, make_event, make_status, make_visit
):
    user = make_user(email="revert-blocked@example.com", username="revert-blocked")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    make_visit(user, event=event, visited_on="2026-07-15")
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "visited"
    assert row.missed_overridden is False


@pytest.mark.django_db
def test_patch_to_missed_rejected_when_visit_record_exists(
    client, make_user, make_event, make_status, make_visit
):
    user = make_user(email="missed-blocked@example.com", username="missed-blocked")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    make_visit(user, event=event, visited_on="2026-07-15")
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "missed"},
        content_type="application/json",
    )

    assert response.status_code == 400
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "visited"


@pytest.mark.django_db
def test_patch_to_planned_allowed_after_visit_record_deleted(
    client, make_user, make_event, make_status, make_visit
):
    """The mis-recorded-data recovery path (delete the record, then revert to
    planned) must stay open — the guard only blocks while a VisitRecord still
    exists for the subject."""
    user = make_user(email="recovery-path@example.com", username="recovery-path")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    visit = make_visit(user, event=event, visited_on="2026-07-15")
    visit.delete()
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 200
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "planned"


# ---------------------------------------------------------------------------
# The VisitRecord invariant above only closed the PATCH path. DELETE is not
# guarded (§6-b Deferred, product decision pending) and creates a fresh row,
# so DELETE followed by a POST could still recreate the exact drift 0016
# corrected: a `planned`/`missed` status row coexisting with a VisitRecord.
# create_user_event_status needs the same _has_visit_record guard.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_rejects_planned_when_visit_record_exists(
    client, make_user, make_event, make_status, make_visit
):
    """Reproduces the delete-then-recreate drift: a visited status row is
    deleted, then a fresh 'planned' creation for the same subject must be
    rejected because its VisitRecord still exists."""
    user = make_user(email="create-blocked@example.com", username="create-blocked")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    make_visit(user, event=event, visited_on="2026-07-15")
    status_id = status.id

    client.force_login(user)
    delete_response = client.delete(f"/api/user-event-statuses/{status_id}/")
    assert delete_response.status_code == 204

    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(user=user, event=event).exists()


@pytest.mark.django_db
def test_create_rejects_missed_when_visit_record_exists(
    client, make_user, make_event, make_status, make_visit
):
    user = make_user(email="create-missed-blocked@example.com", username="create-missed-blocked")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    make_visit(user, event=event, visited_on="2026-07-15")
    status_id = status.id

    client.force_login(user)
    client.delete(f"/api/user-event-statuses/{status_id}/")

    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "missed"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(user=user, event=event).exists()


@pytest.mark.django_db
def test_create_allows_visited_when_visit_record_exists(client, make_user, make_event, make_visit):
    """A fresh 'visited' creation matching an existing VisitRecord is not
    drift — it agrees with the record instead of contradicting it."""
    user = make_user(email="create-visited-ok@example.com", username="create-visited-ok")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    make_visit(user, event=event, visited_on="2026-07-15")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "visited"


@pytest.mark.django_db
def test_create_planned_allowed_without_visit_record(client, make_user, make_event):
    """No-regression baseline: creating 'planned' with no VisitRecord at all
    stays unaffected by the new guard."""
    user = make_user(email="create-planned-ok@example.com", username="create-planned-ok")
    event = make_event(title="Fresh event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_create_rejects_planned_when_visit_record_exists_for_personal_entry(
    client, make_user, make_entry, make_visit
):
    """_has_visit_record covers both subjects (event and personal_entry) —
    the create guard must reject on the personal_entry subject too."""
    user = make_user(email="create-entry-blocked@example.com", username="create-entry-blocked")
    entry = make_entry(user, title="개인 장소")
    make_visit(user, personal_entry=entry, visited_on="2026-07-15")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(user=user, personal_entry=entry).exists()


@pytest.mark.django_db
def test_create_planned_not_blocked_by_other_users_visit_record(client, make_user, make_event, make_visit):
    """Cross-user isolation: another user's VisitRecord for the same event
    must not block this user's own fresh 'planned' creation."""
    owner = make_user(email="cross-owner@example.com", username="cross-owner")
    other = make_user(email="cross-other@example.com", username="cross-other")
    event = make_event(title="Shared event", publish_status=Event.PublishStatus.PUBLISHED)
    make_visit(other, event=event, visited_on="2026-07-15")

    client.force_login(owner)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201
