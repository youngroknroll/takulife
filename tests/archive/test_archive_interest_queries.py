"""아카이브 읽기 계층(archive/queries.py) 단위 테스트 — 찜(EventInterest) 조회.

list_user_interests/user_interest_summary_counts/user_interest_event_ids/
user_interest_count를 검증한다.
"""

from datetime import date, timedelta

import pytest

from archive.queries import (
    list_user_interests,
    user_interest_count,
    user_interest_event_ids,
    user_interest_summary_counts,
)

TODAY = date(2026, 6, 26)

pytestmark = pytest.mark.domain


# ---------------------------------------------------------------------------
# list_user_interests — 사용자로 범위를 좁히고 event를 select_related, 최신순 정렬
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_찜_목록_조회는_사용자로_범위를_좁히고_최신_등록_순으로_정렬한다(make_user, make_event, make_interest):
    user = make_user(username="interest-query-user")
    other = make_user(username="interest-query-other")
    e1 = make_event(title="Interest E1")
    e2 = make_event(title="Interest E2")
    e3 = make_event(title="Interest E3")

    first = make_interest(user, event=e1)
    second = make_interest(user, event=e2)
    make_interest(other, event=e3)

    rows = list(list_user_interests(user))

    assert len(rows) == 2
    assert rows[0].pk == second.pk
    assert rows[1].pk == first.pk
    assert rows[0].event.id == e2.id


# ---------------------------------------------------------------------------
# list_user_interests(q=..., sort=...) — 찜 목록 페이지 검색/정렬 (Phase Q, 찜 브리프 §3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_찜_검색어가_공식_행사_제목에_일치하면_결과에_포함된다(make_user, make_event, make_interest):
    """Q1: 공식 행사 제목에 일치."""
    user = make_user(username="interest-q-title-user")
    matched = make_event(title="벚꽃 축제 특전 판매")
    other = make_event(title="전혀 다른 행사")
    make_interest(user, event=matched)
    make_interest(user, event=other)

    rows = list(list_user_interests(user, q="벚꽃"))

    assert [row.event_id for row in rows] == [matched.id]


@pytest.mark.django_db
def test_찜_검색어가_공식_행사_장소에_일치하면_결과에_포함된다(make_user, make_event, make_interest):
    """Q2: 공식 행사 장소명(location_name)에 일치."""
    user = make_user(username="interest-q-location-user")
    matched = make_event(title="행사 A", location_name="코엑스 전시홀")
    other = make_event(title="행사 B", location_name="킨텍스 전시장")
    make_interest(user, event=matched)
    make_interest(user, event=other)

    rows = list(list_user_interests(user, q="코엑스"))

    assert [row.event_id for row in rows] == [matched.id]


@pytest.mark.django_db
def test_찜_검색어가_비공식_항목_제목에_일치하면_결과에_포함된다(make_user, make_entry, make_interest):
    """Q3: 비공식 항목(PersonalEntry) 제목에 일치."""
    user = make_user(username="interest-q-personal-title-user")
    matched = make_entry(user, title="한정판 굿즈 판매점")
    other = make_entry(user, title="다른 장소")
    make_interest(user, personal_entry=matched)
    make_interest(user, personal_entry=other)

    rows = list(list_user_interests(user, q="한정판"))

    assert [row.personal_entry_id for row in rows] == [matched.id]


@pytest.mark.django_db
def test_찜_검색어가_비공식_항목_장소에_일치하면_결과에_포함된다(make_user, make_entry, make_interest):
    """Q4: 비공식 항목(PersonalEntry) 장소명(location_name)에 일치."""
    user = make_user(username="interest-q-personal-location-user")
    matched = make_entry(user, title="장소 A", location_name="홍대 골목상점")
    other = make_entry(user, title="장소 B", location_name="강남 골목상점")
    make_interest(user, personal_entry=matched)
    make_interest(user, personal_entry=other)

    rows = list(list_user_interests(user, q="홍대"))

    assert [row.personal_entry_id for row in rows] == [matched.id]


@pytest.mark.django_db
def test_찜_정렬_파라미터가_알수없는_값이면_최신_찜순으로_폴백한다(make_user, make_event, make_interest):
    """Q5: 알 수 없는 정렬값은 기본값(-id, 최신순)으로 폴백한다."""
    user = make_user(username="interest-q-sort-fallback-user")
    e1 = make_event(title="정렬 폴백 E1")
    e2 = make_event(title="정렬 폴백 E2")
    first = make_interest(user, event=e1)
    second = make_interest(user, event=e2)

    rows = list(list_user_interests(user, sort="존재하지-않는-정렬"))

    assert [row.pk for row in rows] == [second.pk, first.pk]


@pytest.mark.django_db
def test_찜_정렬_파라미터가_오래된순이면_오래된_찜부터_정렬된다(make_user, make_event, make_interest):
    """Q6: sort="oldest"는 id 오름차순(오래된 찜부터)으로 정렬한다."""
    user = make_user(username="interest-q-sort-oldest-user")
    e1 = make_event(title="오래된순 E1")
    e2 = make_event(title="오래된순 E2")
    first = make_interest(user, event=e1)
    second = make_interest(user, event=e2)

    rows = list(list_user_interests(user, sort="oldest"))

    assert [row.pk for row in rows] == [first.pk, second.pk]


# ---------------------------------------------------------------------------
# user_interest_summary_counts — 찜 목록 요약 통계 (Phase Q, §1 D2/D3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_진행중_찜_통계는_시작일_종료일_양끝과_종료임박_구간을_모두_포함한다(
    make_user, make_event, make_interest
):
    """Q7: ongoing_count는 경계일(시작==오늘, 종료==오늘)과 종료임박 구간(종료가
    CLOSING_SOON_DAYS 이내)을 모두 포함한다(D2 — 행 상태 필터가 셋 다 "진행 중"으로
    표시한다)."""
    user = make_user(username="interest-q7-user")
    starts_today = make_event(
        title="오늘 시작", start_date=TODAY, end_date=TODAY + timedelta(days=10)
    )
    ends_today = make_event(
        title="오늘 종료", start_date=TODAY - timedelta(days=10), end_date=TODAY
    )
    closing_soon = make_event(
        title="종료임박",
        start_date=TODAY - timedelta(days=5),
        end_date=TODAY + timedelta(days=3),
    )
    make_interest(user, event=starts_today)
    make_interest(user, event=ends_today)
    make_interest(user, event=closing_soon)

    counts = user_interest_summary_counts(user, today=TODAY)

    assert counts["ongoing_count"] == 3


@pytest.mark.django_db
def test_진행중_찜_통계는_예정_찜과_종료된_찜을_제외한다(make_user, make_event, make_interest):
    """Q8: ongoing_count는 예정(시작>오늘)과 종료(종료<오늘) 찜을 제외한다."""
    user = make_user(username="interest-q8-user")
    upcoming = make_event(
        title="예정 행사", start_date=TODAY + timedelta(days=5), end_date=TODAY + timedelta(days=6)
    )
    ended = make_event(
        title="종료 행사", start_date=TODAY - timedelta(days=10), end_date=TODAY - timedelta(days=1)
    )
    make_interest(user, event=upcoming)
    make_interest(user, event=ended)

    counts = user_interest_summary_counts(user, today=TODAY)

    assert counts["ongoing_count"] == 0


@pytest.mark.django_db
def test_진행중_찜_통계는_비공식_찜을_제외한다(make_user, make_entry, make_interest):
    """Q9: ongoing_count는 비공식(personal_entry) 찜을 절대 세지 않는다 — 애초에
    진행 기간이 없다."""
    user = make_user(username="interest-q9-user")
    place = make_entry(user, title="비공식 장소")
    make_interest(user, personal_entry=place)

    counts = user_interest_summary_counts(user, today=TODAY)

    assert counts["ongoing_count"] == 0


@pytest.mark.django_db
def test_방문예정_겹침_찜_통계는_파생_상태가_예정인_것만_센다(
    make_user, make_event, make_interest, make_status
):
    """Q10: planned_overlap_count는 연결된 행사의 파생 상태(with_derived_status)가
    planned인 찜만 센다."""
    user = make_user(username="interest-q10-user")
    event = make_event(
        title="방문예정 겹침", start_date=TODAY + timedelta(days=5), end_date=TODAY + timedelta(days=6)
    )
    make_interest(user, event=event)
    make_status(user, event=event, status="planned")

    counts = user_interest_summary_counts(user, today=TODAY)

    assert counts["planned_overlap_count"] == 1


@pytest.mark.django_db
def test_방문예정_겹침_찜_통계는_자동_놓침으로_파생된_찜은_제외한다(
    make_user, make_event, make_interest, make_status
):
    """Q11: 저장된 status가 "planned"라도, 행사 기간이 이미 끝났고(방문기록 없음,
    오버라이드 없음) 파생 상태가 "missed"로 자동 전환된다면
    (archive/querysets.py with_derived_status) planned_overlap_count에 포함되면
    안 된다."""
    user = make_user(username="interest-q11-user")
    ended_event = make_event(
        title="자동_놓침_행사",
        start_date=TODAY - timedelta(days=20),
        end_date=TODAY - timedelta(days=1),
    )
    make_interest(user, event=ended_event)
    make_status(
        user,
        event=ended_event,
        status="planned",
        missed_overridden=False,
    )

    counts = user_interest_summary_counts(user, today=TODAY)

    assert counts["planned_overlap_count"] == 0


@pytest.mark.django_db
def test_방문예정_겹침_찜_통계는_비공식_찜의_예정_상태를_제외한다(
    make_user, make_entry, make_interest, make_status
):
    """Q12: 연결된 PersonalEntry에 status="planned" 행이 있어도 비공식
    (personal_entry) 찜은 planned_overlap_count에서 제외된다."""
    user = make_user(username="interest-q12-user")
    place = make_entry(user, title="비공식 예정 장소")
    make_interest(user, personal_entry=place)
    make_status(user, personal_entry=place, status="planned")

    counts = user_interest_summary_counts(user, today=TODAY)

    assert counts["planned_overlap_count"] == 0


@pytest.mark.django_db
def test_찜_요약_통계_3종은_모두_타인의_찜과_상태를_제외한다(
    make_user, make_event, make_interest, make_status
):
    """Q13: ongoing_count와 planned_overlap_count는 해당 사용자로만 범위가
    좁혀진다 — 다른 사용자의 값이 섞여 들어오지 않는다."""
    user = make_user(username="interest-q13-user")
    other = make_user(username="interest-q13-other")
    other_ongoing = make_event(
        title="타인_진행중", start_date=TODAY, end_date=TODAY + timedelta(days=10)
    )
    other_planned = make_event(
        title="타인_방문예정", start_date=TODAY + timedelta(days=5), end_date=TODAY + timedelta(days=6)
    )
    make_interest(other, event=other_ongoing)
    make_interest(other, event=other_planned)
    make_status(other, event=other_planned, status="planned")

    counts = user_interest_summary_counts(user, today=TODAY)

    assert counts["ongoing_count"] == 0
    assert counts["planned_overlap_count"] == 0


# ---------------------------------------------------------------------------
# user_interest_event_ids — event_id로 범위를 제한한 {event_id: interest_id} 반환
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_이벤트_id_목록으로_범위를_좁히면_해당_행사의_찜_id만_반환한다(make_user, make_event, make_interest):
    user = make_user(username="interest-ids-user")
    other = make_user(username="interest-ids-other")
    e1 = make_event(title="Interest IDs E1")
    e2 = make_event(title="Interest IDs E2")
    e3 = make_event(title="Interest IDs E3")

    i1 = make_interest(user, event=e1)
    make_interest(user, event=e2)
    make_interest(other, event=e3)

    result = user_interest_event_ids(user, event_ids=[e1.id, e3.id])

    assert result == {e1.id: i1.pk}


@pytest.mark.django_db
def test_이벤트_id_범위를_지정하지_않으면_사용자의_모든_찜_id를_반환한다(make_user, make_event, make_interest):
    user = make_user(username="interest-ids-unbound-user")
    e1 = make_event(title="Interest Unbound E1")
    e2 = make_event(title="Interest Unbound E2")

    i1 = make_interest(user, event=e1)
    i2 = make_interest(user, event=e2)

    result = user_interest_event_ids(user)

    assert result == {e1.id: i1.pk, e2.id: i2.pk}


# ---------------------------------------------------------------------------
# user_interest_count
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_찜_총_개수는_본인의_찜만_세고_다른_사용자의_찜은_제외한다(make_user, make_event, make_interest):
    user = make_user(username="interest-count-user")
    other = make_user(username="interest-count-other")
    e1 = make_event(title="Interest Count E1")
    e2 = make_event(title="Interest Count E2")
    e3 = make_event(title="Interest Count E3")

    make_interest(user, event=e1)
    make_interest(user, event=e2)
    make_interest(other, event=e3)

    assert user_interest_count(user) == 2
