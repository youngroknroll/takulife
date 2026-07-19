"""Personal activity month-query contract (dual-calendar Test List §단계 3:
CAL-3-03~11).

archive.queries.list_user_activity_for_month does not exist yet — the whole
file is expected to fail at collection with ImportError until it is added
(mirrors tests/archive/test_activity_log_entry.py's convention).

Assumed return shape — fixed here only to the extent needed to assert
*observable* results (which kind appears on which date), per the task's
explicit "관찰 가능한 결과만 검증, 과도하게 핀하지 말 것" instruction. The
concrete container type (dataclass/NamedTuple/etc.) is the implementer's
choice; this file only relies on attribute access:

- ``list_user_activity_for_month(user, *, year, month, kinds=None)`` returns
  an iterable of items.
- Every item exposes ``.kind`` (str).
- A single-fact-date item (방문 / 굿즈 획득 / 행동성 활동) exposes ``.date``
  (date) and leaves ``.start``/``.end`` as None.
- A period item (일정) exposes ``.start``/``.end`` (date, inclusive) and
  leaves ``.date`` as None.
- kind values used below: ``"schedule"`` (일정 — derived from a planned
  UserEventStatus's linked event period, not an ActivityLogEntry.Kind),
  ``"visit"`` (방문 — VisitRecord.visited_on), ``"goods_acquired"`` (굿즈
  획득 — CollectionItem.acquired_on 우선, 없으면 created_at의 로컬 날짜).
  Every other kind is passed through as the matching ActivityLogEntry.Kind
  value, dated by occurred_at's local date — including the §7.5 잔존 찜
  fallback, which reuses ``ActivityLogEntry.Kind.INTEREST_ADDED`` dated by
  EventInterest.created_at's local date when no log row exists.
- ``kinds`` narrows the result to the given subset of the kind strings above.

These scenarios deliberately build state directly on the models (not via
archive.services), since §단계 2's write-orchestration contract is already
covered in tests/archive/test_activity_log_orchestration.py — this file's
job is the read-side month-window/date-derivation contract only.
"""
from datetime import date, datetime, timedelta
from datetime import timezone as _dt_timezone

import pytest
from django.utils import timezone

from archive.models import ActivityLogEntry, CollectionItem, EventInterest
from archive.queries import list_user_activity_for_month


def _kind_dates(items):
    """Flatten items into a {(kind, date), ...} set, expanding a period item
    (일정) into every date in its inclusive [start, end] range."""
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
# CAL-3-03 — own-user scoping
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
# CAL-3-04 — planned schedule spans the whole event run
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
    make_status(user, event)  # default status=PLANNED

    items = list(list_user_activity_for_month(user, year=2026, month=7))

    assert _kind_dates(items) == {
        ("schedule", date(2026, 7, 5)),
        ("schedule", date(2026, 7, 6)),
        ("schedule", date(2026, 7, 7)),
        ("schedule", date(2026, 7, 8)),
    }


# ---------------------------------------------------------------------------
# CAL-3-05 — an actual visit shows only on visited_on
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
# CAL-3-06 — goods date prefers acquired_on, falls back to created_at
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
# CAL-3-07 — behavioral activity kinds are dated by occurred_at's local date
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
# CAL-3-08 — UTC midnight boundary resolves by KST (Asia/Seoul) localdate
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "occurred_at_utc, expected_date",
    [
        # 2026-07-19T14:59:59Z = KST(+09:00) 2026-07-19 23:59:59
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
# CAL-3-09 — planned/visited/recorded dates never merge
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
# CAL-3-10 — kinds filter narrows the result
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
# CAL-3-11 — no-backfill: pre-existing data still shows by its own fact-date
# rule, with zero ActivityLogEntry rows involved
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
