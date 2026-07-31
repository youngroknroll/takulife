"""개인 활동 월간 조회 계약 (이중 달력 Test List §단계 3: CAL-3-03~11).

list_user_activity_for_month은 아직 구현되지 않아 이 파일 전체가 수집 단계에서
ImportError로 실패하는 것이 정상이다 (test_activity_log_entry.py와 같은 관례).

반환 형태는 "관찰 가능한 결과만 검증, 과도하게 핀하지 말 것" 지침에 따라 검증에
필요한 만큼만 가정한다. 구체 컨테이너 타입은 구현자 재량이고, 이 파일은 속성
접근에만 의존한다:

- ``list_user_activity_for_month(user, *, year, month, kinds=None)``은 아이템의
  이터러블을 반환한다.
- 모든 아이템은 ``.kind``(str)를 갖는다.
- 단일 날짜형 아이템(방문 / 굿즈 획득 / 행동성 활동)은 ``.date``를 갖고
  ``.start``/``.end``는 None이다.
- 기간형 아이템(일정)은 ``.start``/``.end``(포함)를 갖고 ``.date``는 None이다.
- kind 값: ``"schedule"``(일정 — 예정 UserEventStatus에 연결된 행사 기간에서
  파생, ActivityLogEntry 아님), ``"visit"``(방문 — VisitRecord.visited_on),
  ``"goods_acquired"``(굿즈 획득 — CollectionItem.acquired_on 우선, 없으면
  created_at의 로컬 날짜). 그 외 종류는 occurred_at의 로컬 날짜로 표시되는
  ActivityLogEntry.Kind 값 그대로 전달된다 — 로그 행이 없을 때
  ``ActivityLogEntry.Kind.INTEREST_ADDED``를 EventInterest.created_at의 로컬
  날짜로 대체 표시하는 §7.5 잔존 찜 케이스도 포함한다.
- ``kinds``는 위 kind 문자열의 부분집합으로 결과를 좁힌다.

§단계 2의 쓰기 오케스트레이션 계약은 test_activity_log_orchestration.py에서
이미 검증됐으므로, 이 시나리오들은 archive.services를 거치지 않고 모델에 직접
상태를 만든다 — 이 파일은 읽기 쪽 월 범위·날짜 파생 계약만 다룬다.
"""
from datetime import date, datetime, timedelta
from datetime import timezone as _dt_timezone

import pytest
from django.utils import timezone

from archive.activity_calendar_queries import list_user_activity_for_month
from archive.models import ActivityLogEntry, CollectionItem, EventInterest


def _kind_dates(items):
    """아이템을 {(kind, date), ...} 집합으로 펼친다. 기간형 아이템(일정)은
    [start, end] 범위의 모든 날짜로 확장한다."""
    pairs = set()
    for item in items:
        if item.date is not None:
            pairs.add((item.kind, item.date))
        else:
            current = item.start
            while current <= item.end:
                pairs.add((item.kind, current))
                current += timedelta(days=1)
    return pairs


def _aware(*args):
    return timezone.make_aware(datetime(*args))


# ---------------------------------------------------------------------------
# CAL-3-03 — 본인 활동만 조회된다
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
def test_활동_월_조회_결과에는_본인_활동만_포함된다(make_user, make_event, make_interest):
    user_a = make_user(username="cal-activity-owner-a")
    user_b = make_user(username="cal-activity-owner-b")
    event_a = make_event(title="본인 찜 행사")
    event_b = make_event(title="타인 찜 행사")
    interest_a = make_interest(user_a, event=event_a)
    interest_b = make_interest(user_b, event=event_b)
    EventInterest.objects.filter(id__in=[interest_a.id, interest_b.id]).update(
        created_at=_aware(2026, 7, 10, 9, 0)
    )

    items = list(list_user_activity_for_month(user_a, year=2026, month=7))

    assert _kind_dates(items) == {(ActivityLogEntry.Kind.INTEREST_ADDED, date(2026, 7, 10))}


# ---------------------------------------------------------------------------
# CAL-3-04 — 예정 일정은 행사 전체 기간에 표시된다
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_방문_예정_행사는_행사_기간의_모든_날짜에_일정으로_표시된다(
    make_user, make_event, make_status
):
    user = make_user()
    event = make_event(
        title="예정 행사",
        start_date=date(2026, 7, 5),
        end_date=date(2026, 7, 8),
    )
    make_status(user, event)  # 기본값 status=PLANNED

    items = list(list_user_activity_for_month(user, year=2026, month=7))

    assert _kind_dates(items) == {
        ("schedule", date(2026, 7, 5)),
        ("schedule", date(2026, 7, 6)),
        ("schedule", date(2026, 7, 7)),
        ("schedule", date(2026, 7, 8)),
    }


# ---------------------------------------------------------------------------
# CAL-3-05 — 실제 방문은 visited_on 날짜에만 표시된다
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_실제_방문은_visited_on_날짜에만_표시된다(make_user, make_event, make_visit):
    user = make_user()
    event = make_event(title="방문 행사")
    make_visit(user, event=event, visited_on=date(2026, 7, 12))

    items = list(list_user_activity_for_month(user, year=2026, month=7))

    assert _kind_dates(items) == {("visit", date(2026, 7, 12))}


# ---------------------------------------------------------------------------
# CAL-3-06 — 굿즈 날짜는 acquired_on 우선, 없으면 created_at
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "acquired_on, use_created_at_fallback",
    [(date(2026, 7, 3), False), (None, True)],
    ids=["획득일_있음", "획득일_없음"],
)
def test_굿즈_날짜는_획득일을_우선하고_없으면_등록일을_사용한다(
    make_user, make_collection_item, acquired_on, use_created_at_fallback
):
    user = make_user()
    item = make_collection_item(user, name="달력 굿즈", acquired_on=acquired_on)
    if use_created_at_fallback:
        CollectionItem.objects.filter(pk=item.pk).update(created_at=_aware(2026, 7, 20, 18, 0))
        expected_date = date(2026, 7, 20)
    else:
        expected_date = acquired_on

    items = list(list_user_activity_for_month(user, year=2026, month=7))

    assert _kind_dates(items) == {("goods_acquired", expected_date)}


# ---------------------------------------------------------------------------
# CAL-3-07 — 행동성 활동은 occurred_at의 로컬 날짜로 표시된다
# ---------------------------------------------------------------------------


_ACTION_KIND_CASES = {
    "찜": ActivityLogEntry.Kind.INTEREST_ADDED,
    "상태변경": ActivityLogEntry.Kind.STATUS_CHANGED,
    "방문기록작성": ActivityLogEntry.Kind.VISIT_RECORD_CREATED,
    "굿즈등록": ActivityLogEntry.Kind.COLLECTION_ITEM_CREATED,
    "굿즈정리": ActivityLogEntry.Kind.COLLECTION_ITEM_ORGANIZED,
}


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize("kind_id", list(_ACTION_KIND_CASES), ids=list(_ACTION_KIND_CASES))
def test_행동성_활동은_occurred_at의_로컬_날짜에_표시된다(make_user, kind_id):
    user = make_user()
    kind = _ACTION_KIND_CASES[kind_id]
    ActivityLogEntry.objects.create(
        user=user,
        kind=kind,
        occurred_at=_aware(2026, 7, 14, 10, 30),
        subject_label="행동성 활동 테스트",
    )

    items = list(list_user_activity_for_month(user, year=2026, month=7))

    assert _kind_dates(items) == {(kind, date(2026, 7, 14))}


# ---------------------------------------------------------------------------
# CAL-3-08 — UTC 자정 경계는 KST(Asia/Seoul) 로컬 날짜 기준으로 처리된다
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "occurred_at_utc, expected_date",
    [
        # 2026-07-19T14:59:59Z는 KST(+09:00) 기준 2026-07-19 23:59:59다
        # (python3 -c datetime 계산 확인, config/settings.py TIME_ZONE="Asia/Seoul")
        (
            datetime(2026, 7, 19, 14, 59, 59, tzinfo=_dt_timezone.utc),
            date(2026, 7, 19),
        ),
        # 2026-07-19T15:00:00Z = KST 다음날 2026-07-20 00:00:00
        (
            datetime(2026, 7, 19, 15, 0, 0, tzinfo=_dt_timezone.utc),
            date(2026, 7, 20),
        ),
    ],
    ids=["경계_이전", "경계_이후"],
)
def test_occurred_at의_UTC_자정_경계에서도_로컬_날짜_기준으로_표시된다(
    make_user, occurred_at_utc, expected_date
):
    user = make_user()
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.INTEREST_ADDED,
        occurred_at=occurred_at_utc,
        subject_label="자정 경계 테스트",
    )

    items = list(list_user_activity_for_month(user, year=2026, month=7))

    assert _kind_dates(items) == {(ActivityLogEntry.Kind.INTEREST_ADDED, expected_date)}


# ---------------------------------------------------------------------------
# CAL-3-09 — 예정·방문·기록 날짜는 서로 합쳐지지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_방문_예정일과_실제_방문일과_기록_작성일이_다르면_각각_다른_날짜에_나타난다(
    make_user, make_event, make_status, make_visit
):
    user = make_user()
    event = make_event(
        title="예정-방문-기록 분리 행사",
        start_date=date(2026, 7, 5),
        end_date=date(2026, 7, 7),
    )
    make_status(user, event)
    visit = make_visit(user, event=event, visited_on=date(2026, 7, 10))
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.VISIT_RECORD_CREATED,
        occurred_at=_aware(2026, 7, 12, 20, 0),
        subject_label="예정-방문-기록 분리 행사",
        event=event,
        visit_record=visit,
    )

    items = list(list_user_activity_for_month(user, year=2026, month=7))

    assert _kind_dates(items) == {
        ("schedule", date(2026, 7, 5)),
        ("schedule", date(2026, 7, 6)),
        ("schedule", date(2026, 7, 7)),
        ("visit", date(2026, 7, 10)),
        (ActivityLogEntry.Kind.VISIT_RECORD_CREATED, date(2026, 7, 12)),
    }


# ---------------------------------------------------------------------------
# CAL-3-10 — kinds 필터로 결과가 좁혀진다
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_활동_종류_필터를_지정하면_해당_종류만_반환된다(make_user, make_event, make_status):
    user = make_user()
    event = make_event(
        title="필터 대상 행사",
        start_date=date(2026, 7, 5),
        end_date=date(2026, 7, 6),
    )
    make_status(user, event)
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.INTEREST_ADDED,
        occurred_at=_aware(2026, 7, 14, 10, 0),
        subject_label="필터 제외 대상",
    )

    items = list(list_user_activity_for_month(user, year=2026, month=7, kinds=["schedule"]))

    assert _kind_dates(items) == {
        ("schedule", date(2026, 7, 5)),
        ("schedule", date(2026, 7, 6)),
    }


# ---------------------------------------------------------------------------
# CAL-3-11 — 무백필: 로그 행이 하나도 없어도 기존 데이터는 각자의 사실 날짜
# 규칙으로 표시된다
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_활동_이력이_없는_기존_데이터도_각자의_사실_날짜_규칙으로_달력에_표시된다(
    make_user, make_event, make_visit, make_collection_item, make_interest
):
    user = make_user()
    visit_event = make_event(title="무백필 방문 행사")
    make_visit(user, event=visit_event, visited_on=date(2026, 7, 6))
    make_collection_item(user, name="무백필 굿즈", acquired_on=date(2026, 7, 9))
    interest_event = make_event(title="무백필 잔존 찜 행사")
    interest = make_interest(user, event=interest_event)
    EventInterest.objects.filter(pk=interest.pk).update(created_at=_aware(2026, 7, 11, 8, 0))

    items = list(list_user_activity_for_month(user, year=2026, month=7))

    assert _kind_dates(items) == {
        ("visit", date(2026, 7, 6)),
        ("goods_acquired", date(2026, 7, 9)),
        (ActivityLogEntry.Kind.INTEREST_ADDED, date(2026, 7, 11)),
    }
    assert ActivityLogEntry.objects.filter(user=user).count() == 0
