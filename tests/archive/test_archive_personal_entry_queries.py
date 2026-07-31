"""아카이브 읽기 계층(archive/queries.py) 단위 테스트 — 비공식 항목(PersonalEntry) 조회.

list_user_personal_entries/user_personal_entry_counts/
user_personal_interest_ids/user_personal_statuses를 검증한다.
"""

import pytest

from archive.models import EventInterest, PersonalEntry, UserEventStatus
from archive.queries import (
    list_user_personal_entries,
    user_personal_entry_counts,
    user_personal_interest_ids,
    user_personal_statuses,
)

pytestmark = pytest.mark.domain


# ---------------------------------------------------------------------------
# list_user_personal_entries
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_비공식_항목_목록_조회는_사용자로_범위를_좁히고_kind로_추가_필터링한다(make_user, make_entry):
    user = make_user(username="pe-list")
    other = make_user(username="pe-other")
    place = make_entry(user, kind="place", title="P")
    goods = make_entry(user, kind="goods", title="G")
    make_entry(other, kind="place", title="Other P")

    all_entries = list(list_user_personal_entries(user))
    assert place in all_entries
    assert goods in all_entries
    assert len(all_entries) == 2

    only_goods = list(list_user_personal_entries(user, kind="goods"))
    assert only_goods == [goods]


@pytest.mark.django_db
def test_비공식_항목_목록_기본_정렬은_최근_등록순이다(make_user, make_entry):
    user = make_user(username="pe-sort-default")
    older = make_entry(user, title="Older")
    newer = make_entry(user, title="Newer")

    titles = [entry.title for entry in list_user_personal_entries(user)]

    assert titles == [newer.title, older.title]


@pytest.mark.django_db
def test_비공식_항목_목록_정렬을_oldest로_지정하면_오래된_등록순이다(make_user, make_entry):
    user = make_user(username="pe-sort-oldest")
    older = make_entry(user, title="Older")
    newer = make_entry(user, title="Newer")

    titles = [entry.title for entry in list_user_personal_entries(user, sort="oldest")]

    assert titles == [older.title, newer.title]


@pytest.mark.django_db
def test_비공식_항목_목록_미인식_정렬은_기본_최근_등록순으로_폴백한다(make_user, make_entry):
    user = make_user(username="pe-sort-fallback")
    older = make_entry(user, title="Older")
    newer = make_entry(user, title="Newer")

    titles = [
        entry.title
        for entry in list_user_personal_entries(user, sort="not-a-real-option")
    ]

    assert titles == [newer.title, older.title]


# ---------------------------------------------------------------------------
# user_personal_entry_counts (archive/personal/ 요약 카드)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_비공식_항목_집계는_본인의_총_건수만_세고_다른_사용자의_항목은_제외한다(make_user, make_entry):
    user = make_user(username="entry-counts-user")
    other = make_user(username="entry-counts-other")
    make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P1")
    make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P2")
    make_entry(other, kind=PersonalEntry.Kind.PLACE, title="Other P")

    counts = user_personal_entry_counts(user)

    assert counts == {"total_count": 2, "visit_linked_count": 0}


@pytest.mark.django_db
def test_비공식_항목이_없는_사용자의_항목_집계는_0이다(make_user):
    user = make_user(username="entry-counts-empty")

    counts = user_personal_entry_counts(user)

    assert counts == {"total_count": 0, "visit_linked_count": 0}


@pytest.mark.django_db
def test_방문_기록이_연결된_개인_항목_수만_visit_linked_count로_집계된다(
    make_user, make_entry, make_visit
):
    user = make_user(username="entry-counts-visit-linked")
    linked_1 = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P1")
    linked_2 = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P2")
    make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P3")
    make_visit(user, personal_entry=linked_1, visited_on="2026-01-01")
    make_visit(user, personal_entry=linked_2, visited_on="2026-01-02")

    counts = user_personal_entry_counts(user)

    assert counts == {"total_count": 3, "visit_linked_count": 2}


@pytest.mark.django_db
def test_공식_이벤트_방문_기록은_방문_기록_연결_집계에_영향을_주지_않는다(
    make_user, make_entry, make_event, make_visit
):
    user = make_user(username="entry-counts-official-only")
    make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P1")
    event = make_event(title="공식 이벤트")
    make_visit(user, event=event, visited_on="2026-01-01")

    counts = user_personal_entry_counts(user)

    assert counts == {"total_count": 1, "visit_linked_count": 0}


@pytest.mark.django_db
def test_한_항목에_방문_기록이_여러_건이어도_visit_linked_count는_distinct로_1건만_센다(
    make_user, make_entry, make_visit
):
    user = make_user(username="entry-counts-distinct")
    entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P1")
    make_visit(user, personal_entry=entry, visited_on="2026-01-01")
    make_visit(user, personal_entry=entry, visited_on="2026-01-02")

    counts = user_personal_entry_counts(user)

    assert counts == {"total_count": 1, "visit_linked_count": 1}


# ---------------------------------------------------------------------------
# user_personal_interest_ids / user_personal_statuses — 굿즈 행 제외
# (C4 이전 과도기 데이터에 대한 방어적 필터. 이제 굿즈는 찜·상태 대상으로
# 생성할 수 없지만, 이 테스트는 ORM으로 직접 만들어 게이트 도입 이전에 남은
# 데이터를 흉내낸다 — 계획서 §3-3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_비공식_찜_id_조회는_굿즈_kind_개인항목을_제외한다(make_user):
    user = make_user(username="interest-ids-goods")
    place = PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="장소")
    goods = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")
    place_interest = EventInterest.objects.create(user=user, personal_entry=place)
    EventInterest.objects.create(user=user, personal_entry=goods)

    result = user_personal_interest_ids(user)

    assert result == {place.id: place_interest.id}


@pytest.mark.django_db
def test_비공식_상태_조회는_굿즈_kind_개인항목을_제외한다(make_user):
    user = make_user(username="statuses-goods")
    place = PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="장소")
    goods = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")
    place_status = UserEventStatus.objects.create(
        user=user, personal_entry=place, status=UserEventStatus.Status.PLANNED
    )
    UserEventStatus.objects.create(
        user=user, personal_entry=goods, status=UserEventStatus.Status.PLANNED
    )

    result = user_personal_statuses(user)

    assert result == {place.id: (UserEventStatus.Status.PLANNED, place_status.id)}
