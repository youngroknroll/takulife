"""Phase 2: VisitRecord can point at an Event (official) OR a PersonalEntry
(unofficial) — exactly one. Covers the model constraint and the API either/or
validation (including owner-scoping of personal_entry).
"""
import pytest
from django.db import IntegrityError, transaction

from archive.models import PersonalEntry, VisitRecord


# ---------------------------------------------------------------------------
# model constraint — exactly one subject
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_visit_record_accepts_personal_entry_subject(make_user):
    user = make_user(username="vr-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 장소")

    record = VisitRecord.objects.create(
        user=user, personal_entry=entry, visited_on="2026-06-20"
    )

    assert record.event is None
    assert record.personal_entry == entry


@pytest.mark.django_db
def test_visit_record_rejects_both_subjects(make_user, make_event):
    user = make_user(username="vr-both")
    event = make_event(title="Official")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VisitRecord.objects.create(
                user=user, event=event, personal_entry=entry, visited_on="2026-06-20"
            )


@pytest.mark.django_db
def test_visit_record_rejects_no_subject(make_user):
    user = make_user(username="vr-none")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VisitRecord.objects.create(user=user, visited_on="2026-06-20")


# ---------------------------------------------------------------------------
# API — either/or
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_api_create_visit_record_with_personal_entry(client, make_user):
    user = make_user(username="vr-api-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 카페")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"personal_entry": entry.id, "visited_on": "2026-06-21", "short_review": "좋았다"},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["personal_entry"] == entry.id
    assert data["event"] is None


@pytest.mark.django_db
def test_api_create_visit_record_with_event_still_works(client, make_user, make_event):
    user = make_user(username="vr-api-ev")
    event = make_event(title="Official event")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-06-21"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id


@pytest.mark.django_db
def test_api_create_visit_record_requires_exactly_one_subject(client, make_user):
    user = make_user(username="vr-api-none")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"visited_on": "2026-06-21"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_api_cannot_attach_another_users_personal_entry(client, make_user):
    user = make_user(username="vr-api-scope")
    other = make_user(username="vr-api-scope-other")
    theirs = PersonalEntry.objects.create(user=other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"personal_entry": theirs.id, "visited_on": "2026-06-21"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not VisitRecord.objects.filter(personal_entry=theirs).exists()
