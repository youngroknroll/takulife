from datetime import date

import pytest

from archive.models import ActivityLogEntry, UserEventStatus
from events.models import Event

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_게시된_행사에_인증된_사용자가_상태를_등록하면_생성된다(client, make_user, make_event):
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
def test_레거시_me_행사상태_경로는_요청하면_404로_비활성_상태를_유지한다(client, make_user, make_event):
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
def test_행사_상태_목록을_조회하면_현재_사용자_소유_상태만_반환된다(client, make_user, make_event, make_status):
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
def test_행사_상태_목록을_event와_status로_필터링하면_일치하는_항목만_반환된다(client, make_user, make_event, make_status):
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
def test_행사_상태_목록에_허용되지_않는_status_필터를_지정하면_400으로_거부된다(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    event = make_event(title="Event one", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, event, status="planned")

    client.force_login(user)
    response = client.get("/api/user-event-statuses/?status=attended")

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.django_db
def test_다른_사용자의_행사_상태_상세를_조회하면_404로_숨겨진다(client, make_user, make_event, make_status):
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
def test_발행되지_않은_행사에_상태를_등록하면_400으로_거부된다(client, make_user, make_event):
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
def test_허용되지_않는_status_값으로_상태를_등록하면_400으로_거부된다(client, make_user, make_event):
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
def test_이미_존재하는_행사_상태를_다시_등록하면_409_중복_오류가_된다(client, make_user, make_event, make_status):
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
def test_인증된_사용자가_행사_상태를_수정하면_새_상태로_반영된다(client, make_user, make_event, make_status):
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
def test_지난_행사에서_계획으로_되돌리면_missed_overridden이_고정되어_계획_상태를_유지한다(client, make_user, make_event, make_status):
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
def test_행사_상태에_PUT_요청을_보내면_405로_거부되고_기존_값이_보존된다(client, make_user, make_event, make_status):
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
def test_인증된_사용자가_행사_상태를_삭제하면_이후_조회에서_404가_된다(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.delete(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 204
    assert client.get(f"/api/user-event-statuses/{status_id}/").status_code == 404


# ---------------------------------------------------------------------------
# CAL-2-13 — (신설) DELETE must go through remove_user_event_status so a
# status_removed ActivityLogEntry is recorded (perform_destroy wiring
# regression guard, dual-calendar Test List §단계 2)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_상태_삭제_API를_호출하면_status_removed_활동_이력이_기록된다(
    client, make_user, make_event, make_status
):
    user = make_user(email="status-removed-activity@example.com", username="status-removed-activity")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.delete(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 204
    assert (
        ActivityLogEntry.objects.filter(
            user=user, kind=ActivityLogEntry.Kind.STATUS_REMOVED, event=event
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_status_필드_없이_PATCH하면_상태_전환_없이_저장된다(client, make_event, make_user):
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
def test_interested를_status로_등록하려_하면_400으로_거부된다(client, make_user, make_event):
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
def test_방문_기록이_있는_상태에서_계획으로_되돌리려_하면_400으로_거부된다(
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
def test_방문_기록이_있는_상태에서_놓침으로_변경하려_하면_400으로_거부된다(
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
def test_방문_기록을_삭제한_뒤에는_계획으로_되돌리기가_허용된다(
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
def test_방문_기록이_남아있는_상태에서_계획_상태를_새로_생성하려_하면_400으로_거부된다(
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
def test_방문_기록이_남아있는_상태에서_놓침_상태를_새로_생성하려_하면_400으로_거부된다(
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
def test_방문_기록과_일치하는_방문완료_상태를_새로_생성하면_허용된다(client, make_user, make_event, make_visit):
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
def test_방문_기록이_없으면_계획_상태_생성이_영향받지_않는다(client, make_user, make_event):
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
def test_개인_장소의_방문_기록이_있는_상태에서_계획_상태를_생성하려_하면_400으로_거부된다(
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
def test_다른_사용자의_방문_기록은_내_계획_상태_생성을_막지_않는다(client, make_user, make_event, make_visit):
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
