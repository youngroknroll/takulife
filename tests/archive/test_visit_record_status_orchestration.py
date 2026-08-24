"""complete_visit_with_record — 방문 완료와 기록 생성을 함께 처리하는
오케스트레이션 (컬렉션 도메인 설계안 §3-4, PR-C3, F-02).

계획에서 승인된 (a)~(e) 계약을 다룬다: VisitRecord는 상태 대상이 "visited"와
불일치한 채로는 존재할 수 없다.
"""
import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from archive.models import ActivityLogEntry, PersonalEntry, UserEventStatus, VisitRecord
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
# RACE-02 — 상태 행 생성이 동시 삽입과 충돌해도(별도 커넥션에서 경쟁 행을
# 실제로 커밋한 뒤 재호출로 진짜 유니크 제약 IntegrityError 유발) 기존
# 행을 재조회해 방문 완료 처리를 정상 완료한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_상태_행_생성이_동시_삽입과_충돌하면_기존_행을_재조회해_방문_완료_처리를_정상_완료한다(
    monkeypatch, make_user, make_event
):
    # 단일 커넥션 안에서 원본 create를 두 번 호출하는 방식은 전부 같은
    # 트랜잭션의 세이브포인트 안에서 일어난다. create_user_event_status가
    # IntegrityError를 잡아 세이브포인트를 롤백하면, 그 세이브포인트 안에서
    # 만든 "경쟁" 행도 함께 사라져 재조회가 아무것도 찾지 못한다 — 재조회-
    # 발견 경로 자체를 검증할 수 없다. 실제 동시 요청처럼 경쟁 행이 메인
    # 트랜잭션과 무관하게 이미 커밋되어 살아 있어야 하므로, 별도 스레드의
    # 별도 DB 커넥션으로 경쟁 행을 즉시 커밋시킨다. 이 때문에
    # transaction=True로 실제 트랜잭션 커밋/격리를 켜야 한다(기본
    # django_db는 테스트 전체를 하나의 롤백용 트랜잭션으로 감싸 다른
    # 커넥션이 그 미커밋 상태를 볼 수 없다).
    import threading

    from django.db import connection

    user = make_user()
    event = make_event()

    original_create = UserEventStatus.objects.create
    call_state = {"fired": False}

    def create_competing_row_on_separate_connection():
        try:
            UserEventStatus.objects.create(
                user=user, event=event, status=UserEventStatus.Status.VISITED
            )
        finally:
            # 스레드가 열어둔 커넥션은 자동으로 정리되지 않으므로 직접 닫는다.
            connection.close()

    def create_with_simulated_race(**kwargs):
        if not call_state["fired"]:
            call_state["fired"] = True
            thread = threading.Thread(target=create_competing_row_on_separate_connection)
            thread.start()
            thread.join()
            # 경쟁 행이 이미 커밋된 상태에서 같은 인자로 다시 INSERT를
            # 시도해, DB가 실제로 발생시키는 유니크 제약 IntegrityError를
            # 유발한다.
            return original_create(**kwargs)
        return original_create(**kwargs)

    monkeypatch.setattr(
        "archive.services.UserEventStatus.objects.create", create_with_simulated_race
    )

    complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    assert UserEventStatus.objects.filter(user=user, event=event).count() == 1
    status_row = UserEventStatus.objects.get(user=user, event=event)
    assert status_row.status == UserEventStatus.Status.VISITED
    assert VisitRecord.objects.filter(user=user, event=event).count() == 1
    # 경쟁 행은 스레드가 UserEventStatus.objects.create로 직접 만들었고
    # create_user_event_status/mark_visited를 거치지 않았으므로 그 자체로는
    # STATUS_CHANGED 활동이나 EVENT_MARKED_VISITED 분석 이벤트를 남기지
    # 않는다. 메인 호출은 재조회로 이미 VISITED인 행을 발견해
    # mark_visited를 건너뛰므로, 이 프로세스 안에서는 두 이벤트 모두
    # 0회가 맞는 기대값이다(승자 쪽 이벤트는 이 테스트 밖의 다른 요청
    # 프로세스에서 이미 기록됐을 상황을 모사한 것일 뿐, 이 테스트
    # 안에서는 재현하지 않는다).
    assert (
        ActivityLogEntry.objects.filter(kind=ActivityLogEntry.Kind.STATUS_CHANGED).count() == 0
    )
    assert (
        ActivityLogEntry.objects.filter(
            kind=ActivityLogEntry.Kind.VISIT_RECORD_CREATED
        ).count()
        == 1
    )
    assert (
        AnalyticsEvent.objects.filter(
            event_name=AnalyticsEvent.EventName.EVENT_MARKED_VISITED
        ).count()
        == 0
    )
    assert (
        AnalyticsEvent.objects.filter(
            event_name=AnalyticsEvent.EventName.VISIT_RECORD_CREATED
        ).count()
        == 1
    )


# ---------------------------------------------------------------------------
# RACE-01 — 초기 상태 행 조회는 FOR UPDATE 잠금 아래에서 실행되어야 한다.
# 단일 커넥션 테스트로는 실제 병렬 경쟁을 재현할 수 없으므로(위 RACE-02
# 주석과 같은 한계), 캡처된 SQL에 FOR UPDATE가 실제로 발생하는지 보는
# 대리 계약으로 검증한다(tests/drafts/test_discovery_runs.py의
# claim FOR UPDATE 계약과 같은 선례 패턴).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.contract
@pytest.mark.parametrize(
    "existing_status",
    [None, UserEventStatus.Status.PLANNED],
    ids=["상태_행_없음", "참석_예정_상태_존재"],
)
def test_방문_완료_처리_시_상태_행_조회는_FOR_UPDATE_잠금_아래에서_실행된다(
    existing_status, make_user, make_event, make_status
):
    user = make_user()
    event = make_event()
    if existing_status is not None:
        make_status(user, event, status=existing_status)

    table_name = UserEventStatus._meta.db_table

    with CaptureQueriesContext(connection) as ctx:
        complete_visit_with_record(user=user, event=event, visited_on="2026-07-15")

    status_select_queries = [
        query
        for query in ctx.captured_queries
        if "SELECT" in query["sql"].upper() and table_name.upper() in query["sql"].upper()
    ]
    assert status_select_queries, "상태 테이블을 조회하는 SELECT 쿼리가 존재해야 한다"
    assert any("FOR UPDATE" in query["sql"].upper() for query in status_select_queries)


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
