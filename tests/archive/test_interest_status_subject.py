"""Phase 3: EventInterest (찜) and UserEventStatus (방문예정) can point at an
Event (official) OR a PersonalEntry (unofficial) — exactly one.

Covers the model constraints (exactly-one + conditional uniqueness) and the API
either/or validation, including owner-scoping of personal_entry and event
back-compat. Mirrors test_visit_record_subject.py (Phase 2).
"""
import pytest
from django.db import IntegrityError, transaction

from archive.models import EventInterest, PersonalEntry, UserEventStatus


# ---------------------------------------------------------------------------
# EventInterest — model constraints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_interest_accepts_personal_entry_subject(make_user):
    user = make_user(username="ei-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 장소")

    interest = EventInterest.objects.create(user=user, personal_entry=entry)

    assert interest.event is None
    assert interest.personal_entry == entry


@pytest.mark.django_db
def test_interest_rejects_both_subjects(make_user, make_event):
    user = make_user(username="ei-both")
    event = make_event(title="Official")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventInterest.objects.create(user=user, event=event, personal_entry=entry)


@pytest.mark.django_db
def test_interest_rejects_no_subject(make_user):
    user = make_user(username="ei-none")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventInterest.objects.create(user=user)


@pytest.mark.django_db
def test_interest_event_subject_still_unique_per_user(make_user, make_event):
    user = make_user(username="ei-ev-unique")
    event = make_event(title="E")

    EventInterest.objects.create(user=user, event=event)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventInterest.objects.create(user=user, event=event)


@pytest.mark.django_db
def test_interest_personal_subject_unique_per_user(make_user):
    user = make_user(username="ei-pe-unique")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    EventInterest.objects.create(user=user, personal_entry=entry)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventInterest.objects.create(user=user, personal_entry=entry)


# ---------------------------------------------------------------------------
# UserEventStatus — model constraints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_status_accepts_personal_entry_subject(make_user):
    user = make_user(username="ues-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 장소")

    status = UserEventStatus.objects.create(
        user=user, personal_entry=entry, status="planned"
    )

    assert status.event is None
    assert status.personal_entry == entry


@pytest.mark.django_db
def test_status_rejects_both_subjects(make_user, make_event):
    user = make_user(username="ues-both")
    event = make_event(title="Official")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserEventStatus.objects.create(
                user=user, event=event, personal_entry=entry, status="planned"
            )


@pytest.mark.django_db
def test_status_rejects_no_subject(make_user):
    user = make_user(username="ues-none")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserEventStatus.objects.create(user=user, status="planned")


@pytest.mark.django_db
def test_status_event_subject_still_unique_per_user(make_user, make_event):
    user = make_user(username="ues-ev-unique")
    event = make_event(title="E")

    UserEventStatus.objects.create(user=user, event=event, status="planned")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserEventStatus.objects.create(user=user, event=event, status="visited")


@pytest.mark.django_db
def test_status_personal_subject_unique_per_user(make_user):
    user = make_user(username="ues-pe-unique")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    UserEventStatus.objects.create(user=user, personal_entry=entry, status="planned")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserEventStatus.objects.create(
                user=user, personal_entry=entry, status="visited"
            )


# ---------------------------------------------------------------------------
# EventInterest API — either/or
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_api_create_interest_with_personal_entry(client, make_user):
    user = make_user(username="ei-api-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 카페")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"personal_entry": entry.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["personal_entry"] == entry.id
    assert data["event"] is None


@pytest.mark.django_db
def test_api_create_interest_with_event_still_works(client, make_user, make_event):
    user = make_user(username="ei-api-ev")
    event = make_event(title="Official event")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id


@pytest.mark.django_db
def test_api_create_interest_requires_exactly_one_subject(client, make_user):
    user = make_user(username="ei-api-none")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_api_interest_cannot_attach_another_users_personal_entry(client, make_user):
    user = make_user(username="ei-api-scope")
    other = make_user(username="ei-api-scope-other")
    theirs = PersonalEntry.objects.create(user=other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"personal_entry": theirs.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not EventInterest.objects.filter(personal_entry=theirs).exists()


@pytest.mark.django_db
def test_api_interest_duplicate_personal_entry_returns_409(client, make_user):
    user = make_user(username="ei-api-dup")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    client.force_login(user)
    client.post(
        "/api/event-interests/",
        {"personal_entry": entry.id},
        content_type="application/json",
    )
    response = client.post(
        "/api/event-interests/",
        {"personal_entry": entry.id},
        content_type="application/json",
    )

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# UserEventStatus API — either/or
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_api_create_status_with_personal_entry(client, make_user):
    user = make_user(username="ues-api-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 장소")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["personal_entry"] == entry.id
    assert data["event"] is None
    assert data["status"] == "planned"


@pytest.mark.django_db
def test_api_create_status_with_event_still_works(client, make_user, make_event):
    user = make_user(username="ues-api-ev")
    event = make_event(title="Official event")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id


@pytest.mark.django_db
def test_api_create_status_requires_exactly_one_subject(client, make_user):
    user = make_user(username="ues-api-none")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_api_status_cannot_attach_another_users_personal_entry(client, make_user):
    user = make_user(username="ues-api-scope")
    other = make_user(username="ues-api-scope-other")
    theirs = PersonalEntry.objects.create(user=other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": theirs.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(personal_entry=theirs).exists()


@pytest.mark.django_db
def test_api_interest_rejects_goods_personal_entry(client, make_user):
    """GOODS is no longer a valid archive-action subject (collection domain
    plan §3-3) — only PLACE personal entries may be favourited."""
    user = make_user(username="ei-api-goods")
    entry = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"personal_entry": entry.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not EventInterest.objects.filter(personal_entry=entry).exists()


@pytest.mark.django_db
def test_api_status_duplicate_personal_entry_returns_409(client, make_user):
    user = make_user(username="ues-api-dup")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    client.force_login(user)
    client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "planned"},
        content_type="application/json",
    )
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_api_status_rejects_goods_personal_entry_subject(client, make_user):
    """GOODS is no longer a valid archive-action subject (collection domain
    plan §3-3) — only PLACE personal entries may carry a status."""
    user = make_user(username="ues-api-goods")
    entry = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(personal_entry=entry).exists()
