"""complete_visit_with_record — visit-completion + record-creation
orchestration (collection domain design plan §3-4, PR-C3, F-02).

Covers the (a)/(b)/(c)/(d)/(e) contract approved in the plan: a visit record
can never exist while its status subject disagrees with "visited".
"""
import uuid

import pytest

from archive.models import PersonalEntry, UserEventStatus, VisitRecord
from archive.services import complete_visit_with_record
from core.models import AnalyticsEvent

pytestmark = pytest.mark.domain


# ---------------------------------------------------------------------------
# CP1 — no existing status row: auto-create visited
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_상태_기록이_없는_행사를_방문_완료_처리하면_방문_완료_상태와_기록이_함께_생성된다(make_user, make_event):
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
def test_참석_예정_상태에서_방문_완료_처리하면_같은_상태_행이_방문_완료로_전환된다(make_user, make_event, make_status):
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
def test_불참_상태에서_방문_완료_처리하면_상태가_방문_완료로_전환된다(make_user, make_event, make_status):
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
def test_이미_방문_완료된_행사를_다시_방문_완료_처리하면_상태는_그대로_유지되고_기록만_추가된다(
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
    ids=["상태_없음", "참석_예정", "불참"],
)
def test_상태_없음_참석_예정_불참_중_어디서_시작해도_방문_완료_처리_시_방문_완료_이벤트가_한_번만_기록된다(
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
# INTG-BE-04 — bfcache duplicate-creation track: complete_visit_with_record
# needs its own client_token idempotency guard, mirroring create_visit_record
# and create_collection_item (INTG-BE-01-VR/CI). A replayed "완료 처리" submit
# (e.g. a bfcache-restored page re-POSTing the same form) must not fire a
# second status transition or a second VisitRecord/analytics event.
# complete_visit_with_record does not yet accept client_token, so this call
# is expected to raise TypeError until the orchestration guard lands.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_같은_클라이언트_토큰으로_방문_완료_처리를_두_번_요청하면_상태_전환과_기록_생성_모두_중복되지_않는다(
    make_user, make_event
):
    user = make_user()
    event = make_event()
    token = uuid.uuid4()

    # Given: no status row yet for this (user, event) pair.
    assert not UserEventStatus.objects.filter(user=user, event=event).exists()

    complete_visit_with_record(
        user=user, event=event, visited_on="2026-07-15", client_token=token
    )

    status_row = UserEventStatus.objects.get(user=user, event=event)
    assert status_row.status == UserEventStatus.Status.VISITED
    original_updated_at = status_row.updated_at

    # When: the same client_token is replayed (e.g. a bfcache-restored page
    # re-submitting the same "완료 처리" form).
    complete_visit_with_record(
        user=user, event=event, visited_on="2026-07-16", client_token=token
    )

    # Then: the status row is untouched (proves mark_visited did not fire a
    # second time) and no second VisitRecord or analytics event was created.
    status_row.refresh_from_db()
    assert status_row.status == UserEventStatus.Status.VISITED
    assert status_row.updated_at == original_updated_at
    assert UserEventStatus.objects.filter(user=user, event=event).count() == 1
    assert VisitRecord.objects.filter(user=user, event=event).count() == 1
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
def test_비공식_장소를_방문_완료_처리하면_해당_장소_기준으로_상태와_기록이_생성된다(make_user):
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
def test_상태_저장이_실패하면_방문_기록_생성도_함께_롤백된다(monkeypatch, make_user, make_event):
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
def test_방문_기록이_있는데_상태만_참석_예정으로_남아있으면_마이그레이션이_방문_완료로_보정한다(
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


# ---------------------------------------------------------------------------
# CP10-bis — 0016 corrects a status row using only *that same user's* own
# VisitRecord (§6-b Deferred: "0016 크로스 유저 격리 명시 테스트"). Another
# user's VisitRecord for the same subject must never leak across accounts.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_다른_사용자의_방문_기록은_마이그레이션_보정_대상에서_제외된다(
    make_user, make_event, make_status, make_visit
):
    import importlib

    migration_module = importlib.import_module(
        "archive.migrations.0016_fix_planned_status_with_existing_visit_record"
    )
    fix_planned_status_with_existing_visit_record = (
        migration_module.fix_planned_status_with_existing_visit_record
    )

    owner = make_user(username="owner-a2")
    other_user = make_user(username="other-a2")
    event = make_event()
    owner_status = make_status(owner, event, status=UserEventStatus.Status.PLANNED)
    make_visit(other_user, event=event, visited_on="2026-07-15")

    from django.apps import apps as real_apps

    fix_planned_status_with_existing_visit_record(real_apps, None)

    owner_status.refresh_from_db()
    assert owner_status.status == UserEventStatus.Status.PLANNED


# ---------------------------------------------------------------------------
# Domain gate CRITICAL fix — analytics persistence failure inside the shared
# atomic() must not poison the outer transaction (core.analytics record_event
# needs its own savepoint so a DB error there can't fail subsequent domain
# writes with TransactionManagementError).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_분석_이벤트_기록이_실패해도_방문_완료_상태_전환과_기록_저장은_유지된다(
    monkeypatch, make_user, make_event, make_status
):
    user = make_user()
    event = make_event()
    status_row = make_status(user, event, status=UserEventStatus.Status.PLANNED)

    # A monkeypatch that raises in pure Python (without ever hitting the DB)
    # never poisons the real PostgreSQL transaction — it doesn't reproduce
    # the bug. Force a *genuine* DB-level error instead: event_name is a
    # VARCHAR(32) column, so a 100-char value overflows it at the database,
    # which is exactly the kind of failure that aborts the ambient PG
    # transaction if it isn't isolated behind its own savepoint.
    def raise_real_database_error(**kwargs):
        AnalyticsEvent(
            event_name="x" * 100, user_key="", target_type="", target_id=None, context={}
        ).save()

    monkeypatch.setattr(
        "core.analytics.AnalyticsEvent.objects.create", raise_real_database_error
    )

    # Must not raise — analytics persistence failure must not break the
    # domain action it is attached to.
    complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    status_row.refresh_from_db()
    assert status_row.status == UserEventStatus.Status.VISITED
    assert VisitRecord.objects.filter(user=user, event=event).count() == 1
