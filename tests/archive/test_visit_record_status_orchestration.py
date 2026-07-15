"""complete_visit_with_record — visit-completion + record-creation
orchestration (collection domain design plan §3-4, PR-C3, F-02).

Covers the (a)/(b)/(c)/(d)/(e) contract approved in the plan: a visit record
can never exist while its status subject disagrees with "visited".
"""
import pytest

from archive.models import PersonalEntry, UserEventStatus, VisitRecord
from archive.services import complete_visit_with_record
from core.models import AnalyticsEvent


# ---------------------------------------------------------------------------
# CP1 — no existing status row: auto-create visited
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_existing_status_auto_creates_visited(make_user, make_event):
    user = make_user()
    event = make_event()

    complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    status_row = UserEventStatus.objects.get(user=user, event=event)
    assert status_row.status == UserEventStatus.Status.VISITED
    assert VisitRecord.objects.filter(user=user, event=event).count() == 1


# ---------------------------------------------------------------------------
# CP2 — existing planned row: auto-transition to visited, same row
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_existing_planned_status_auto_transitions_to_visited(make_user, make_event, make_status):
    user = make_user()
    event = make_event()
    status_row = make_status(user, event, status=UserEventStatus.Status.PLANNED)

    complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    status_row.refresh_from_db()
    assert status_row.status == UserEventStatus.Status.VISITED
    assert UserEventStatus.objects.filter(user=user, event=event).count() == 1


# ---------------------------------------------------------------------------
# CP3 — existing missed row: also transitions to visited
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_existing_missed_status_transitions_to_visited(make_user, make_event, make_status):
    user = make_user()
    event = make_event()
    status_row = make_status(user, event, status=UserEventStatus.Status.MISSED)

    complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    status_row.refresh_from_db()
    assert status_row.status == UserEventStatus.Status.VISITED


# ---------------------------------------------------------------------------
# CP4 — already visited: status untouched, repeat record allowed
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_repeat_visit_on_already_visited_event_allowed_no_status_churn(
    make_user, make_event, make_status
):
    user = make_user()
    event = make_event()
    status_row = make_status(user, event, status=UserEventStatus.Status.VISITED)
    original_updated_at = status_row.updated_at

    complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    status_row.refresh_from_db()
    assert status_row.updated_at == original_updated_at
    assert (
        AnalyticsEvent.objects.filter(
            event_name=AnalyticsEvent.EventName.EVENT_MARKED_VISITED
        ).count()
        == 0
    )
    assert VisitRecord.objects.filter(user=user, event=event).count() == 1

    complete_visit_with_record(user=user, event=event, visited_on="2026-07-16")

    status_row.refresh_from_db()
    assert status_row.updated_at == original_updated_at
    assert VisitRecord.objects.filter(user=user, event=event).count() == 2


# ---------------------------------------------------------------------------
# CP5 — each starting branch records EVENT_MARKED_VISITED exactly once
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "starting_status",
    [None, UserEventStatus.Status.PLANNED, UserEventStatus.Status.MISSED],
)
def test_each_branch_records_marked_visited_exactly_once(
    make_user, make_event, make_status, starting_status
):
    user = make_user()
    event = make_event()
    if starting_status is not None:
        make_status(user, event, status=starting_status)

    complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    assert (
        AnalyticsEvent.objects.filter(
            event_name=AnalyticsEvent.EventName.EVENT_MARKED_VISITED
        ).count()
        == 1
    )
    assert (
        AnalyticsEvent.objects.filter(
            event_name=AnalyticsEvent.EventName.VISIT_RECORD_CREATED
        ).count()
        == 1
    )


# ---------------------------------------------------------------------------
# CP7 — personal_entry (place) subject gets identical treatment (approved)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_existing_status_auto_creates_visited_for_personal_entry_subject(make_user):
    user = make_user()
    entry = PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 장소")

    complete_visit_with_record(user=user, personal_entry=entry, visited_on="2026-07-15")

    status_row = UserEventStatus.objects.get(user=user, personal_entry=entry)
    assert status_row.status == UserEventStatus.Status.VISITED
    assert VisitRecord.objects.filter(user=user, personal_entry=entry).count() == 1


# ---------------------------------------------------------------------------
# CP8 — atomicity: status write failure rolls back the visit record too
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_status_write_failure_rolls_back_visit_record(monkeypatch, make_user, make_event):
    from django.db import IntegrityError

    user = make_user()
    event = make_event()

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("archive.services.UserEventStatus.objects.create", raise_integrity_error)

    from archive.services import DuplicateUserEventStatusError

    with pytest.raises(DuplicateUserEventStatusError):
        complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    assert VisitRecord.objects.filter(user=user, event=event).count() == 0
    assert UserEventStatus.objects.filter(user=user, event=event).count() == 0


# ---------------------------------------------------------------------------
# CP10 — data migration corrects pre-existing planned/missed drift
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_data_migration_fixes_planned_status_with_existing_record(
    make_user, make_event, make_status, make_visit
):
    import importlib

    migration_module = importlib.import_module(
        "archive.migrations.0016_fix_planned_status_with_existing_visit_record"
    )
    fix_planned_status_with_existing_visit_record = (
        migration_module.fix_planned_status_with_existing_visit_record
    )

    user = make_user()
    mismatched_event = make_event()
    mismatched_status = make_status(user, mismatched_event, status=UserEventStatus.Status.PLANNED)
    make_visit(user, event=mismatched_event, visited_on="2026-07-15")

    untouched_event = make_event()
    untouched_status = make_status(user, untouched_event, status=UserEventStatus.Status.PLANNED)

    from django.apps import apps as real_apps

    fix_planned_status_with_existing_visit_record(real_apps, None)

    mismatched_status.refresh_from_db()
    untouched_status.refresh_from_db()
    assert mismatched_status.status == UserEventStatus.Status.VISITED
    assert untouched_status.status == UserEventStatus.Status.PLANNED
