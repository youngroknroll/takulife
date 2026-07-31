"""complete_visit_with_record — 방문 완료와 기록 생성을 함께 처리하는
오케스트레이션 (컬렉션 도메인 설계안 §3-4, PR-C3, F-02).

계획에서 승인된 (a)~(e) 계약을 다룬다: VisitRecord는 상태 대상이 "visited"와
불일치한 채로는 존재할 수 없다.
"""
import uuid

import pytest

from archive.models import PersonalEntry, UserEventStatus, VisitRecord
from archive.services import complete_visit_with_record
from core.models import AnalyticsEvent

pytestmark = pytest.mark.domain


# ---------------------------------------------------------------------------
# CP1 — 기존 상태 행이 없으면 visited 상태를 자동 생성한다
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
# CP2 — 기존 planned 행은 같은 행에서 visited로 자동 전환된다
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
# CP3 — 기존 missed 행도 visited로 전환된다
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
# CP4 — 이미 visited면 상태는 그대로, 기록만 반복 추가된다
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
# CP5 — 시작 상태가 무엇이든 EVENT_MARKED_VISITED는 정확히 한 번만 기록된다
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
# INTG-BE-04 — bfcache 중복 생성 트랙: complete_visit_with_record도
# create_visit_record/create_collection_item(INTG-BE-01-VR/CI)처럼 자체
# client_token 멱등성 가드가 필요하다. bfcache로 복원된 페이지가 같은 폼을
# 재전송해도 상태 전환이나 기록/분석 이벤트가 중복 생성되면 안 된다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_같은_클라이언트_토큰으로_방문_완료_처리를_두_번_요청하면_상태_전환과_기록_생성_모두_중복되지_않는다(
    make_user, make_event
):
    user = make_user()
    event = make_event()
    token = uuid.uuid4()

    # Given: 이 (user, event) 쌍에 대한 상태 행이 아직 없다.
    assert not UserEventStatus.objects.filter(user=user, event=event).exists()

    complete_visit_with_record(
        user=user, event=event, visited_on="2026-07-15", client_token=token
    )

    status_row = UserEventStatus.objects.get(user=user, event=event)
    assert status_row.status == UserEventStatus.Status.VISITED
    original_updated_at = status_row.updated_at

    # When: 같은 client_token이 재전송된다(예: bfcache로 복원된 페이지가
    # 같은 "완료 처리" 폼을 다시 제출).
    complete_visit_with_record(
        user=user, event=event, visited_on="2026-07-16", client_token=token
    )

    # Then: 상태 행은 그대로다(mark_visited가 두 번째로 실행되지 않았음을
    # 증명) — 두 번째 VisitRecord나 분석 이벤트도 생기지 않았다.
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
# CP7 — personal_entry(장소) 대상도 동일하게 처리된다 (승인됨)
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
# CP8 — 원자성: 상태 저장 실패 시 방문 기록 생성도 함께 롤백된다
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
# CP10 — 데이터 마이그레이션이 기존 planned/missed 불일치를 보정한다
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
# CP10-bis — 0016은 오직 *같은 사용자 본인*의 VisitRecord로만 상태 행을
# 보정한다 (§6-b Deferred: "0016 크로스 유저 격리 명시 테스트"). 같은 대상에
# 대한 다른 사용자의 VisitRecord가 계정을 넘어 영향을 주면 안 된다.
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
# 도메인 게이트 CRITICAL 수정 — 공유 atomic() 안에서 분석 이벤트 저장이
# 실패해도 바깥 트랜잭션을 오염시키면 안 된다 (core.analytics의
# record_event는 자체 세이브포인트가 있어야 이후 도메인 쓰기가
# TransactionManagementError로 실패하지 않는다).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_분석_이벤트_기록이_실패해도_방문_완료_상태_전환과_기록_저장은_유지된다(
    monkeypatch, make_user, make_event, make_status
):
    user = make_user()
    event = make_event()
    status_row = make_status(user, event, status=UserEventStatus.Status.PLANNED)

    # 순수 파이썬에서만 예외를 던지는 monkeypatch는 DB를 건드리지 않아 실제
    # PostgreSQL 트랜잭션을 오염시키지 못해 버그를 재현하지 못한다. 대신 진짜
    # DB 오류를 강제한다: event_name은 VARCHAR(32)라 100자 값이 DB 단에서
    # 넘쳐, 세이브포인트로 격리되지 않으면 트랜잭션을 중단시키는 종류의
    # 실패를 재현한다.
    def raise_real_database_error(**kwargs):
        AnalyticsEvent(
            event_name="x" * 100, user_key="", target_type="", target_id=None, context={}
        ).save()

    monkeypatch.setattr(
        "core.analytics.AnalyticsEvent.objects.create", raise_real_database_error
    )

    # 예외가 나면 안 된다 — 분석 이벤트 저장 실패가 붙어 있는 도메인 동작을
    # 깨서는 안 된다.
    complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    status_row.refresh_from_db()
    assert status_row.status == UserEventStatus.Status.VISITED
    assert VisitRecord.objects.filter(user=user, event=event).count() == 1
