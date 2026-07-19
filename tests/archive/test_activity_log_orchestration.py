"""Write-side ActivityLogEntry orchestration (dual-calendar Test List §단계 2:
CAL-2-01~02, 2-04~12; CAL-2-03/2-13 live in the EventInterest/UserEventStatus
API test files instead — see that plan for the full 13-scenario map).

archive.services.remove_event_interest does not exist yet — CAL-2-02 is
expected to fail at collection/call time with ImportError/AttributeError
until it lands. The other scenarios call already-existing service functions
that do not yet write ActivityLogEntry rows, so they are expected to fail
with AssertionError (0 rows instead of 1) until the write orchestration is
added to each service.
"""
import uuid

import pytest
from django.db import IntegrityError

from archive.models import ActivityLogEntry, EventInterest, UserEventStatus, VisitRecord
from archive.services import (
    DuplicateUserEventStatusError,
    complete_visit_with_record,
    create_collection_item,
    create_event_interest,
    create_user_event_status,
    create_visit_record,
    mark_missed,
    mark_visited,
    remove_event_interest,
    revert_to_planned,
    update_collection_item,
)


# ---------------------------------------------------------------------------
# CAL-2-01 — create_event_interest writes interest_added
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_찜을_추가하면_interest_added_활동_이력이_기록된다(make_user, make_event):
    user = make_user()
    event = make_event(title="찜 추가 이벤트")

    create_event_interest(user=user, event=event)

    entries = ActivityLogEntry.objects.filter(
        user=user, kind=ActivityLogEntry.Kind.INTEREST_ADDED
    )
    assert entries.count() == 1
    entry = entries.get()
    assert entry.event_id == event.id
    assert entry.subject_label


# ---------------------------------------------------------------------------
# CAL-2-02 — (신규) remove_event_interest writes interest_removed and deletes
# the row
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_찜을_해제하면_interest_removed_활동_이력이_기록되고_찜_행은_삭제된다(
    make_user, make_event, make_interest
):
    user = make_user()
    event = make_event(title="찜 해제 이벤트")
    interest = make_interest(user, event=event)
    interest_id = interest.id

    remove_event_interest(interest=interest)

    assert not EventInterest.objects.filter(pk=interest_id).exists()
    entries = ActivityLogEntry.objects.filter(
        user=user, kind=ActivityLogEntry.Kind.INTEREST_REMOVED
    )
    assert entries.count() == 1
    entry = entries.get()
    assert entry.event_id == event.id
    assert entry.subject_label


# ---------------------------------------------------------------------------
# CAL-2-04 — first status creation writes status_changed with {"to": ...}
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_상태를_처음_생성하면_status_changed_활동_이력이_기록된다(make_user, make_event):
    user = make_user()
    event = make_event(title="상태 최초 생성 이벤트")

    create_user_event_status(user=user, event=event, status=UserEventStatus.Status.PLANNED)

    entries = ActivityLogEntry.objects.filter(
        user=user, kind=ActivityLogEntry.Kind.STATUS_CHANGED
    )
    assert entries.count() == 1
    entry = entries.get()
    assert entry.event_id == event.id
    assert entry.change_summary == {"to": "planned"}


# ---------------------------------------------------------------------------
# CAL-2-05 — status transition functions write status_changed with
# {"from": ..., "to": ...}
# ---------------------------------------------------------------------------


_TRANSITION_FUNCTIONS = {
    "mark_visited": mark_visited,
    "mark_missed": mark_missed,
    "revert_to_planned": revert_to_planned,
}


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "starting_status, transition_name, expected_change_summary",
    [
        (
            UserEventStatus.Status.PLANNED,
            "mark_visited",
            {"from": "planned", "to": "visited"},
        ),
        (
            UserEventStatus.Status.PLANNED,
            "mark_missed",
            {"from": "planned", "to": "missed"},
        ),
        (
            UserEventStatus.Status.MISSED,
            "revert_to_planned",
            {"from": "missed", "to": "planned"},
        ),
    ],
    ids=["방문완료전환", "불참전환", "예정복귀전환"],
)
def test_상태_전환_함수를_호출하면_status_changed_활동_이력이_기록된다(
    make_user, make_event, make_status, starting_status, transition_name, expected_change_summary
):
    user = make_user()
    event = make_event(title=f"상태 전환 이벤트 {transition_name}")
    status_row = make_status(user, event, status=starting_status)

    _TRANSITION_FUNCTIONS[transition_name](user_event_status=status_row)

    entries = ActivityLogEntry.objects.filter(
        user=user, kind=ActivityLogEntry.Kind.STATUS_CHANGED
    )
    assert entries.count() == 1
    assert entries.get().change_summary == expected_change_summary


# ---------------------------------------------------------------------------
# CAL-2-06 — a no-op transition (already visited -> mark_visited again)
# writes nothing
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_이미_방문완료인_상태에_방문완료_전환을_다시_요청하면_활동_이력이_새로_생성되지_않는다(
    make_user, make_event, make_status
):
    user = make_user()
    event = make_event(title="이미 방문완료 이벤트")
    status_row = make_status(user, event, status=UserEventStatus.Status.VISITED)

    mark_visited(user_event_status=status_row)

    assert (
        ActivityLogEntry.objects.filter(
            user=user, kind=ActivityLogEntry.Kind.STATUS_CHANGED
        ).count()
        == 0
    )


# ---------------------------------------------------------------------------
# CAL-2-07 — create_collection_item writes collection_item_created
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_컬렉션_아이템을_생성하면_collection_item_created_활동_이력이_기록된다(make_user):
    user = make_user()

    item = create_collection_item(user=user, name="아크릴 스탠드")

    entries = ActivityLogEntry.objects.filter(
        user=user, kind=ActivityLogEntry.Kind.COLLECTION_ITEM_CREATED
    )
    assert entries.count() == 1
    entry = entries.get()
    assert entry.collection_item_id == item.id
    assert entry.subject_label


# ---------------------------------------------------------------------------
# CAL-2-08 — an actual organize-field change writes collection_item_organized
# with only the changed allowed field in change_summary
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_name, initial_value, updated_value",
    [
        ("quantity", 1, 3),
        ("acquired_on", None, "2026-07-01"),
    ],
    ids=["수량_변경", "획득일_변경"],
)
def test_정리_대상_필드를_실제로_수정하면_collection_item_organized_활동_이력이_기록된다(
    make_user, make_collection_item, field_name, initial_value, updated_value
):
    user = make_user()
    item = make_collection_item(user, **{field_name: initial_value})

    update_collection_item(item=item, **{field_name: updated_value})

    entries = ActivityLogEntry.objects.filter(
        user=user, kind=ActivityLogEntry.Kind.COLLECTION_ITEM_ORGANIZED
    )
    assert entries.count() == 1
    entry = entries.get()
    assert entry.collection_item_id == item.id
    # Core-key check only (§ no over-pinning) — the changed allowed field is
    # the only key present, whatever its serialized value type turns out to be.
    assert set(entry.change_summary) == {field_name}


# ---------------------------------------------------------------------------
# CAL-2-09 — a non-organize field change, or a same-value save, writes
# nothing
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "update_kwargs",
    [{"memo": "새 메모"}, {"quantity": 1}],
    ids=["정리대상아닌_필드만_수정", "실제값_변경없음"],
)
def test_정리_이력이_생성되지_않는_수정_요청을_보내도_collection_item_organized가_기록되지_않는다(
    make_user, make_collection_item, update_kwargs
):
    user = make_user()
    item = make_collection_item(user, quantity=1, memo="원래 메모")

    update_collection_item(item=item, **update_kwargs)

    assert (
        ActivityLogEntry.objects.filter(
            user=user, kind=ActivityLogEntry.Kind.COLLECTION_ITEM_ORGANIZED
        ).count()
        == 0
    )


# ---------------------------------------------------------------------------
# CAL-2-10 — complete_visit_with_record writes visit_record_created
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_방문_기록을_생성하면_visit_record_created_활동_이력이_기록된다(make_user, make_event):
    user = make_user()
    event = make_event(title="방문 기록 생성 이벤트")

    record = complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    entries = ActivityLogEntry.objects.filter(
        user=user, kind=ActivityLogEntry.Kind.VISIT_RECORD_CREATED
    )
    assert entries.count() == 1
    assert entries.get().visit_record_id == record.id


# ---------------------------------------------------------------------------
# CAL-2-11 — a status-save failure rolls back the visit record *and* the
# activity log entry together (CP8 failure-injection technique, mirrored
# from tests/archive/test_visit_record_status_orchestration.py)
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
def test_상태_저장이_실패하면_방문_기록과_활동_이력_모두_함께_롤백된다(
    monkeypatch, make_user, make_event
):
    user = make_user()
    event = make_event()

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("archive.services.UserEventStatus.objects.create", raise_integrity_error)

    with pytest.raises(DuplicateUserEventStatusError):
        complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    assert VisitRecord.objects.filter(user=user, event=event).count() == 0
    assert UserEventStatus.objects.filter(user=user, event=event).count() == 0
    assert ActivityLogEntry.objects.filter(user=user).count() == 0


# ---------------------------------------------------------------------------
# CAL-2-12 — a replayed client_token create is exactly-once for the activity
# log entry too, and operation_key carries the client_token value
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "target",
    ["굿즈_생성", "방문기록_생성"],
    ids=["굿즈_생성", "방문기록_생성"],
)
def test_동일_operation_key로_생성을_재시도해도_활동_이력이_중복_생성되지_않는다(
    make_user, make_event, target
):
    user = make_user()
    token = uuid.uuid4()

    if target == "굿즈_생성":
        create_collection_item(user=user, name="멱등 생성 굿즈", client_token=token)
        create_collection_item(user=user, name="멱등 생성 굿즈", client_token=token)
        kind = ActivityLogEntry.Kind.COLLECTION_ITEM_CREATED
    else:
        event = make_event(title="멱등 생성 방문 기록 이벤트")
        create_visit_record(user=user, event=event, visited_on="2026-07-15", client_token=token)
        create_visit_record(user=user, event=event, visited_on="2026-07-16", client_token=token)
        kind = ActivityLogEntry.Kind.VISIT_RECORD_CREATED

    entries = ActivityLogEntry.objects.filter(user=user, kind=kind, operation_key=token)
    assert entries.count() == 1
