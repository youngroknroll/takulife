"""쓰기 쪽 ActivityLogEntry 오케스트레이션 (이중 달력 Test List §단계 2:
CAL-2-01~02, 2-04~12; CAL-2-03/2-13은 EventInterest/UserEventStatus API 테스트
파일에 있다 — 전체 13개 시나리오 지도는 그 계획서 참조).

archive.services.remove_event_interest는 아직 없어 CAL-2-02는 수집/호출
시점에 ImportError/AttributeError로 실패하는 것이 정상이다. 나머지 시나리오는
이미 존재하는 서비스 함수를 호출하지만 아직 ActivityLogEntry를 쓰지 않으므로,
각 서비스에 쓰기 오케스트레이션이 추가되기 전까지 AssertionError(0건이어야
할 자리에 1건 없음)로 실패하는 것이 정상이다.
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
# CAL-2-01 — create_event_interest는 interest_added를 기록한다
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
# CAL-2-02 — (신규) remove_event_interest는 interest_removed를 기록하고 행을
# 삭제한다
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
# CAL-2-04 — 상태를 처음 생성하면 status_changed에 {"to": ...}가 기록된다
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
# CAL-2-05 — 상태 전환 함수는 status_changed에 {"from": ..., "to": ...}를
# 기록한다
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
# CAL-2-06 — 이미 방문완료 상태에 mark_visited를 다시 호출해도(무동작 전환)
# 아무것도 기록되지 않는다
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
# CAL-2-07 — create_collection_item은 collection_item_created를 기록한다
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
# CAL-2-08 — 정리 대상 필드가 실제로 바뀌면 collection_item_organized가
# 바뀐 필드만 change_summary에 담아 기록된다
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
    # 과도한 핀 금지 원칙에 따라 키만 확인한다 — 직렬화된 값 타입과 무관하게
    # 바뀐 필드 하나만 존재하면 된다.
    assert set(entry.change_summary) == {field_name}


# ---------------------------------------------------------------------------
# CAL-2-09 — 정리 대상이 아닌 필드 수정이나 값이 같은 저장은 아무것도
# 기록하지 않는다
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
# CAL-2-10 — complete_visit_with_record는 visit_record_created를 기록한다
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
# CAL-2-11 — 상태 저장 실패 시 방문 기록과 활동 이력이 함께 롤백된다
# (CP8 실패 주입 기법, tests/archive/test_visit_record_status_orchestration.py
# 에서 그대로 가져옴)
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
# CAL-2-12 — client_token을 재전송한 생성 요청도 활동 이력이 정확히 한 번만
# 기록되고, operation_key에 client_token 값이 그대로 담긴다
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
