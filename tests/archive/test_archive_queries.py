"""아카이브 읽기 계층(archive/queries.py) 단위 테스트."""

from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone

from archive.models import CollectionItem, EventInterest, PersonalEntry, UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_STATUS_SLUGS,
    list_items_acquired_at_visit,
    list_user_collection_items,
    list_user_interests,
    list_user_personal_entries,
    list_user_planned_events,
    list_user_statuses,
    list_user_unrecorded_visited_statuses,
    list_user_upcoming_planned_events,
    list_user_visit_records,
    list_visit_records_for_personal_entry,
    user_collection_item_filter_values,
    user_collection_item_summary_counts,
    user_collection_item_work_title_facets,
    user_interest_count,
    user_interest_event_ids,
    user_interest_summary_counts,
    user_personal_entry_counts,
    user_personal_interest_ids,
    user_personal_statuses,
    user_status_counts,
    user_visit_record_counts,
    user_visit_record_photo_count,
)

TODAY = date(2026, 6, 26)

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_상태_기록이_없는_사용자의_상태별_집계는_모든_슬러그가_0으로_채워진다(make_user):
    user = make_user(username="counts-empty")

    counts = user_status_counts(user)

    assert set(counts) == set(ARCHIVE_STATUS_SLUGS)
    assert all(value == 0 for value in counts.values())


@pytest.mark.django_db
def test_상태별_집계는_본인의_상태만_세고_다른_사용자의_기록은_제외한다(make_user, make_event, make_status):
    user = make_user(username="counts-user")
    other = make_user(username="counts-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    make_status(user, event=e1, status="planned")
    make_status(user, event=e2, status="visited")
    make_status(other, event=e1, status="planned")

    counts = user_status_counts(user)

    assert counts["planned"] == 1
    assert counts["visited"] == 1
    assert counts["missed"] == 0


@pytest.mark.django_db
def test_상태_목록_조회는_사용자로_범위를_좁히고_상태값으로_추가_필터링한다(make_user, make_event, make_status):
    user = make_user(username="list-status-user")
    other = make_user(username="list-status-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    make_status(user, event=e1, status="planned")
    make_status(user, event=e2, status="visited")
    make_status(other, event=e1, status="planned")

    assert list_user_statuses(user).count() == 2
    planned_only = list_user_statuses(user, "planned")
    assert planned_only.count() == 1
    assert planned_only.first().event_id == e1.id


# ---------------------------------------------------------------------------
# list_user_statuses(sort=...) — F-1 정렬 파라미터화
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_정렬_파라미터가_등록순이면_결과가_등록일_내림차순으로_정렬된다(
    make_user, make_event, make_status
):
    user = make_user(username="sort-created-at-user")
    event_a = make_event(title="먼저 등록, 나중 수정")
    event_b = make_event(title="나중 등록, 이후 수정 없음")

    status_a = make_status(user, event=event_a, status="planned")
    status_b = make_status(user, event=event_b, status="planned")

    UserEventStatus.objects.filter(pk=status_a.pk).update(
        created_at=timezone.make_aware(datetime(2026, 6, 1)),
        updated_at=timezone.make_aware(datetime(2026, 6, 20)),
    )
    UserEventStatus.objects.filter(pk=status_b.pk).update(
        created_at=timezone.make_aware(datetime(2026, 6, 15)),
        updated_at=timezone.make_aware(datetime(2026, 6, 10)),
    )

    created_at_sorted = list(list_user_statuses(user, sort="created_at"))
    assert [row.pk for row in created_at_sorted] == [status_b.pk, status_a.pk]

    default_sorted = list(list_user_statuses(user))
    assert [row.pk for row in default_sorted] == [status_a.pk, status_b.pk]


@pytest.mark.django_db
def test_정렬_파라미터가_알수없는_값이면_기본_정렬로_폴백한다(
    make_user, make_event, make_status
):
    user = make_user(username="sort-fallback-user")
    event_a = make_event(title="먼저 등록, 나중 수정")
    event_b = make_event(title="나중 등록, 이후 수정 없음")

    status_a = make_status(user, event=event_a, status="planned")
    status_b = make_status(user, event=event_b, status="planned")

    UserEventStatus.objects.filter(pk=status_a.pk).update(
        created_at=timezone.make_aware(datetime(2026, 6, 1)),
        updated_at=timezone.make_aware(datetime(2026, 6, 20)),
    )
    UserEventStatus.objects.filter(pk=status_b.pk).update(
        created_at=timezone.make_aware(datetime(2026, 6, 15)),
        updated_at=timezone.make_aware(datetime(2026, 6, 10)),
    )

    fallback_sorted = list(list_user_statuses(user, sort="not-a-real-option"))
    assert [row.pk for row in fallback_sorted] == [status_a.pk, status_b.pk]


# ---------------------------------------------------------------------------
# list_user_statuses(...) — F-2 리뷰 인용(visit_record_id / review_text 주석)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "subject_kind",
    ["event", "personal_entry"],
    ids=["공식_이벤트_주체", "비공식_개인항목_주체"],
)
def test_상태_행에_해당_주체의_최신_방문기록_리뷰와_id가_함께_담긴다(
    subject_kind, make_user, make_event, make_entry, make_status, make_visit
):
    user = make_user(username=f"review-subject-{subject_kind}")

    if subject_kind == "event":
        subject = make_event(title="방문 행사")
        status = make_status(user, event=subject, status="visited")
        visit = make_visit(
            user, event=subject, visited_on="2026-06-20", short_review="정말 좋았어요"
        )
    else:
        subject = make_entry(user, title="방문 개인 항목")
        status = make_status(user, personal_entry=subject, status="visited")
        visit = make_visit(
            user, personal_entry=subject, visited_on="2026-06-20", short_review="정말 좋았어요"
        )

    row = list_user_statuses(user).get(pk=status.pk)

    assert row.review_text == "정말 좋았어요"
    assert row.visit_record_id == visit.id


@pytest.mark.django_db
def test_방문기록이_없는_상태_행은_리뷰와_방문기록_id가_비어있다(
    make_user, make_event, make_status
):
    user = make_user(username="review-no-visit")
    event = make_event(title="방문기록 없는 행사")
    status = make_status(user, event=event, status="planned")

    row = list_user_statuses(user).get(pk=status.pk)

    assert row.review_text is None
    assert row.visit_record_id is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tie_break",
    [False, True],
    ids=["방문일이_다른_경우", "방문일이_동률인_경우"],
)
def test_같은_주체에_방문기록이_여러_건이면_최신_1건의_리뷰가_선택된다(
    tie_break, make_user, make_event, make_status, make_visit
):
    user = make_user(username=f"review-latest-{'tie' if tie_break else 'diff'}")
    event = make_event(title="방문 행사")
    status = make_status(user, event=event, status="visited")

    if not tie_break:
        # 방문일이 다른 경우: 더 나중 방문일(2026-06-20)의 리뷰가 선택되어야 한다.
        first_visit = make_visit(
            user, event=event, visited_on="2026-06-01", short_review="1차"
        )
        second_visit = make_visit(
            user, event=event, visited_on="2026-06-20", short_review="2차"
        )
        expected_review = "2차"
        expected_visit = second_visit
    else:
        # 방문일이 동률인 경우: 같은 visited_on=2026-06-20 이므로 -id 가 결정력을
        # 가져야 한다 — 더 큰 pk(나중에 저장된 쪽)의 리뷰가 선택되어야 한다.
        first_visit = make_visit(
            user, event=event, visited_on="2026-06-20", short_review="먼저 저장"
        )
        second_visit = make_visit(
            user, event=event, visited_on="2026-06-20", short_review="나중 저장"
        )
        expected_review = "나중 저장"
        expected_visit = second_visit

    assert first_visit.pk < second_visit.pk  # 생성 순서(pk) 명시적 확인

    row = list_user_statuses(user).get(pk=status.pk)

    assert row.review_text == expected_review
    assert row.visit_record_id == expected_visit.id


# ---------------------------------------------------------------------------
# list_user_unrecorded_visited_statuses (collection-first home: 미완성 기록)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문완료_상태에_방문기록이_없으면_미기록_방문완료_목록에_포함된다(
    make_user, make_event, make_status
):
    user = make_user(username="unrecorded-basic")
    event = make_event(title="다녀온 행사")
    status = make_status(user, event=event, status="visited")

    rows = list(list_user_unrecorded_visited_statuses(user))

    assert status in rows


@pytest.mark.django_db
def test_방문완료_상태에_방문기록이_이미_있으면_미기록_방문완료_목록에서_제외된다(
    make_user, make_event, make_status, make_visit
):
    user = make_user(username="unrecorded-has-record")
    event = make_event(title="기록 있는 행사")
    status = make_status(user, event=event, status="visited")
    make_visit(user, event=event, visited_on="2026-06-01")

    rows = list(list_user_unrecorded_visited_statuses(user))

    assert status not in rows


@pytest.mark.django_db
def test_이벤트_주체와_마찬가지로_개인항목_주체의_방문완료_상태도_방문기록이_생기면_미기록_방문완료_목록에서_제외된다(
    make_user, make_entry, make_status, make_visit
):
    """Exists 서브쿼리가 event/personal_entry 매치를 OR로(AND가 아니라) 합성하는지
    지키는 회귀 가드다: AND로 합치면 personal_entry 주체 행에서 OuterRef("event")를
    NULL과 비교하게 되어 항상 거짓이 되고, 방문 기록이 생겨도 이 행이 영영
    "미기록"으로 남아버린다."""
    user = make_user(username="unrecorded-personal")
    entry = make_entry(user, title="비공식 방문지")
    status = make_status(user, personal_entry=entry, status="visited")

    before = list(list_user_unrecorded_visited_statuses(user))
    assert status in before

    make_visit(user, personal_entry=entry, visited_on="2026-06-01")

    after = list(list_user_unrecorded_visited_statuses(user))
    assert status not in after


@pytest.mark.django_db
def test_예정_상태이거나_다른_사용자의_방문완료_상태는_미기록_방문완료_목록에서_제외된다(
    make_user, make_event, make_status
):
    user = make_user(username="unrecorded-scope")
    other = make_user(username="unrecorded-scope-other")
    e1 = make_event(title="예정 행사")
    e2 = make_event(title="타 유저 방문 행사")

    planned = make_status(user, event=e1, status="planned")
    others_visited = make_status(other, event=e2, status="visited")

    rows = list(list_user_unrecorded_visited_statuses(user))

    assert planned not in rows
    assert others_visited not in rows


@pytest.mark.django_db
def test_방문기록_목록_조회는_사용자로_범위를_좁히고_최신_방문일_순으로_정렬한다(make_user, make_event, make_visit):
    user = make_user(username="list-visit-user")
    other = make_user(username="list-visit-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    older = make_visit(user, event=e1, visited_on="2026-05-01")
    newer = make_visit(user, event=e2, visited_on="2026-06-01")
    make_visit(other, event=e1, visited_on="2026-06-15")

    rows = list(list_user_visit_records(user))

    assert [r.id for r in rows] == [newer.id, older.id]


# ---------------------------------------------------------------------------
# list_user_visit_records(sort=...) — 다녀온 기록 정렬 파라미터화
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_정렬_파라미터가_오래된순이면_결과가_방문일_오름차순으로_정렬된다(
    make_user, make_event, make_visit
):
    user = make_user(username="sort-oldest-visit-user")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    older = make_visit(user, event=e1, visited_on="2026-05-01")
    newer = make_visit(user, event=e2, visited_on="2026-06-01")

    rows = list(list_user_visit_records(user, sort="oldest"))

    assert [r.id for r in rows] == [older.id, newer.id]


@pytest.mark.django_db
def test_오래된순_정렬에서_방문일이_같으면_id_오름차순으로_동률을_가른다(
    make_user, make_event, make_visit
):
    user = make_user(username="sort-oldest-tie-visit-user")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    lower_id = make_visit(user, event=e1, visited_on="2026-05-01")
    higher_id = make_visit(user, event=e2, visited_on="2026-05-01")

    rows = list(list_user_visit_records(user, sort="oldest"))

    assert [r.id for r in rows] == [lower_id.id, higher_id.id]


@pytest.mark.django_db
def test_정렬_파라미터가_알수없는_값이면_기본_정렬로_폴백한다_방문기록(
    make_user, make_event, make_visit
):
    user = make_user(username="sort-fallback-visit-user")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    older = make_visit(user, event=e1, visited_on="2026-05-01")
    newer = make_visit(user, event=e2, visited_on="2026-06-01")

    rows = list(list_user_visit_records(user, sort="not-a-real-option"))

    assert [r.id for r in rows] == [newer.id, older.id]


@pytest.mark.django_db
def test_공식_행사만_필터링하면_비공식_개인항목에_연결된_방문기록은_제외된다(make_event, make_user):
    user = make_user()
    event = make_event(title="공식 방문")
    entry = PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 방문"
    )
    VisitRecord.objects.create(user=user, event=event, visited_on="2026-01-01")
    VisitRecord.objects.create(user=user, personal_entry=entry, visited_on="2026-01-02")

    official = list(list_user_visit_records(user, official=True))

    assert all(r.event_id is not None for r in official)
    assert len(official) == 1


@pytest.mark.django_db
def test_해당_방문에_연결된_굿즈만_등록순으로_반환한다(
    make_user, make_event, make_visit, make_collection_item
):
    user = make_user()
    record = make_visit(user, event=make_event(), visited_on="2026-05-26")
    other_record = make_visit(
        user, event=make_event(title="다른 방문"), visited_on="2026-05-27"
    )

    first_item = make_collection_item(user, name="첫 번째 굿즈", visit_record=record)
    second_item = make_collection_item(user, name="두 번째 굿즈", visit_record=record)
    make_collection_item(user, name="다른 방문의 굿즈", visit_record=other_record)
    make_collection_item(user, name="방문 미연결 굿즈")

    result = list(list_items_acquired_at_visit(record))

    assert result == [first_item, second_item]


@pytest.mark.django_db
def test_한_장소에_연결된_방문_기록만_최신순으로_반환한다(
    make_user, make_entry, make_event, make_visit
):
    """PD-9a: 대상 PersonalEntry에 연결된 방문만 반환하며, 최신 visited_on 순으로
    정렬한다(list_user_visit_records 기본 정렬 -visited_on, -id와 동일)."""
    user = make_user()
    entry = make_entry(user, title="대상 장소")
    other_entry = make_entry(user, title="다른 장소")
    older = make_visit(user, personal_entry=entry, visited_on="2026-01-01")
    newer = make_visit(user, personal_entry=entry, visited_on="2026-02-01")
    make_visit(user, personal_entry=other_entry, visited_on="2026-03-01")
    make_visit(user, event=make_event(), visited_on="2026-04-01")

    result = list(list_visit_records_for_personal_entry(entry))

    assert [record.id for record in result] == [newer.id, older.id]


# ---------------------------------------------------------------------------
# ARCHIVE_STATUS_SLUGS에는 더 이상 "interested"가 없다
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_아카이브_상태_슬러그_목록에는_찜_상태가_포함되지_않는다(django_user_model):
    assert "interested" not in ARCHIVE_STATUS_SLUGS
    assert "planned" in ARCHIVE_STATUS_SLUGS
    assert "visited" in ARCHIVE_STATUS_SLUGS
    assert "missed" in ARCHIVE_STATUS_SLUGS


# ---------------------------------------------------------------------------
# user_status_counts — DB에 행이 있어도 interested는 집계에서 제외
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_상태별_집계_결과에는_찜_키가_포함되지_않는다(make_user):
    user = make_user(username="counts-no-interested")
    counts = user_status_counts(user)
    assert "interested" not in counts


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


# ---------------------------------------------------------------------------
# list_user_planned_events (방문 기록 추가 시 선택 가능한 행사 집합)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문예정_행사_목록은_본인이_예정_등록한_게시된_행사만_반환한다(make_user, make_event, make_draft_event, make_status):
    user = make_user(username="planner")
    other = make_user(username="planner-other")
    planned = make_event(title="Planned")
    visited = make_event(title="Visited")
    missed = make_event(title="Missed")
    others_planned = make_event(title="Others planned")
    draft_planned = make_draft_event(title="Draft planned")

    make_status(user, event=planned, status="planned")
    make_status(user, event=visited, status="visited")
    make_status(user, event=missed, status="missed")
    make_status(user, event=draft_planned, status="planned")
    make_status(other, event=others_planned, status="planned")

    events = list(list_user_planned_events(user))

    assert planned in events
    assert visited not in events
    assert missed not in events
    assert others_planned not in events
    assert draft_planned not in events


# ---------------------------------------------------------------------------
# list_user_upcoming_planned_events (collection-first home: 다가오는 예정 행사)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_다가오는_예정_행사_목록은_본인이_예정_등록한_게시된_행사로_범위를_좁힌다(
    make_user, make_event, make_draft_event, make_status
):
    user = make_user(username="upcoming-planner")
    other = make_user(username="upcoming-planner-other")
    future = TODAY + timedelta(days=5)
    planned = make_event(title="Planned", start_date=future)
    visited = make_event(title="Visited", start_date=future)
    missed = make_event(title="Missed", start_date=future)
    others_planned = make_event(title="Others planned", start_date=future)
    draft_planned = make_draft_event(title="Draft planned", start_date=future)

    make_status(user, event=planned, status="planned")
    make_status(user, event=visited, status="visited")
    make_status(user, event=missed, status="missed")
    make_status(user, event=draft_planned, status="planned")
    make_status(other, event=others_planned, status="planned")

    events = list(list_user_upcoming_planned_events(user, today=TODAY))

    assert planned in events
    assert visited not in events
    assert missed not in events
    assert others_planned not in events
    assert draft_planned not in events


@pytest.mark.django_db
def test_다가오는_예정_행사_목록은_오늘과_지난_시작일을_제외하고_내일_이후만_포함한다(
    make_user, make_event, make_status
):
    user = make_user(username="upcoming-boundary")
    yesterday_event = make_event(title="Yesterday", start_date=TODAY - timedelta(days=1))
    today_event = make_event(title="Today", start_date=TODAY)
    tomorrow_event = make_event(title="Tomorrow", start_date=TODAY + timedelta(days=1))

    make_status(user, event=yesterday_event, status="planned")
    make_status(user, event=today_event, status="planned")
    make_status(user, event=tomorrow_event, status="planned")

    events = list(list_user_upcoming_planned_events(user, today=TODAY))

    assert yesterday_event not in events
    assert today_event not in events  # 오늘은 제외됨(gt이지 gte가 아님)
    assert tomorrow_event in events


@pytest.mark.django_db
def test_다가오는_예정_행사_목록은_시작일이_이른_순으로_정렬된다(
    make_user, make_event, make_status
):
    user = make_user(username="upcoming-order")
    third = make_event(title="Third", start_date=TODAY + timedelta(days=30))
    first = make_event(title="First", start_date=TODAY + timedelta(days=1))
    second = make_event(title="Second", start_date=TODAY + timedelta(days=10))

    make_status(user, event=third, status="planned")
    make_status(user, event=first, status="planned")
    make_status(user, event=second, status="planned")

    titles = [e.title for e in list_user_upcoming_planned_events(user, today=TODAY)]

    assert titles == ["First", "Second", "Third"]


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
# user_visit_record_counts (archive/visits/ 요약 카드)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문기록_집계는_본인의_총_건수와_후기가_있는_건수를_함께_반환한다(
    make_user, make_event, make_visit
):
    user = make_user(username="visit-counts-user")
    other = make_user(username="visit-counts-other")
    e1 = make_event(title="VC E1")
    e2 = make_event(title="VC E2")
    e3 = make_event(title="VC E3")

    make_visit(user, event=e1, visited_on="2026-01-01", short_review="좋았음")
    make_visit(user, event=e2, visited_on="2026-01-02", short_review="")
    make_visit(other, event=e3, visited_on="2026-01-03", short_review="다른 사용자")

    counts = user_visit_record_counts(user)

    assert counts == {"total_count": 2, "memo_count": 1}


@pytest.mark.django_db
def test_방문기록이_없는_사용자의_방문기록_집계는_0이다(make_user):
    user = make_user(username="visit-counts-empty")

    counts = user_visit_record_counts(user)

    assert counts == {"total_count": 0, "memo_count": 0}


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
# list_user_collection_items (PR-C1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_컬렉션_아이템_목록_조회는_소유자로_범위를_좁힌다(make_user):
    user = make_user(username="ci-query-owner")
    other = make_user(username="ci-query-other")
    mine = CollectionItem.objects.create(user=user, name="내 굿즈")
    CollectionItem.objects.create(user=other, name="남의 굿즈")

    items = list(list_user_collection_items(user))

    assert items == [mine]


# ---------------------------------------------------------------------------
# list_user_collection_items 필터 (PR-C5, CP16~22). `duplicate`/`tradeable`은
# quantity/tradeable_quantity에서 파생된 값이다 — CollectionItem에는 별도의
# duplicate_count나 tradeable 플래그 필드가 없다(§3-1).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_작품명_필터는_완전_일치하는_항목만_반환한다(make_user):
    user = make_user(username="ci-query-work-title")
    match = CollectionItem.objects.create(user=user, name="일치", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="불일치", work_title="작품 B")

    items = list(list_user_collection_items(user, work_title="작품 A"))

    assert items == [match]


@pytest.mark.django_db
def test_중복_필터는_별도_필드_없이_수량_2개_이상_여부로_판정된다(make_user):
    """`duplicate=True`는 quantity >= 2인 행을 선택한다 — 별도의 duplicate_count
    필드는 없다(§3-1)."""
    user = make_user(username="ci-query-duplicate")
    two = CollectionItem.objects.create(user=user, name="둘", quantity=2)
    one = CollectionItem.objects.create(user=user, name="하나", quantity=1)

    assert list(list_user_collection_items(user, duplicate=True)) == [two]
    assert list(list_user_collection_items(user, duplicate=False)) == [one]
    assert not hasattr(two, "duplicate_count")


@pytest.mark.django_db
def test_교환가능_필터는_별도_필드_없이_교환가능_수량_1개_이상_여부로_판정된다(
    make_user,
):
    """`tradeable=True`는 tradeable_quantity > 0인 행을 선택한다 — 별도의
    플래그 필드는 없다(§3-1)."""
    user = make_user(username="ci-query-tradeable")
    tradeable = CollectionItem.objects.create(
        user=user, name="교환 가능", quantity=3, tradeable_quantity=1
    )
    not_tradeable = CollectionItem.objects.create(
        user=user, name="교환 불가", quantity=3, tradeable_quantity=0
    )

    assert list(list_user_collection_items(user, tradeable=True)) == [tradeable]
    assert list(list_user_collection_items(user, tradeable=False)) == [not_tradeable]


@pytest.mark.django_db
def test_보유_필터는_별도_필드_없이_수량_1개_이상_여부로_판정된다(make_user):
    """`owned=True`는 quantity > 0인 행을 선택한다 — duplicate/tradeable과
    같은 파생 필터 패턴으로, 별도의 owned 플래그 필드는 없다(§3-1)."""
    user = make_user(username="ci-query-owned")
    held = CollectionItem.objects.create(user=user, name="가진 것", quantity=3)
    not_held = CollectionItem.objects.create(user=user, name="안 가진 것", quantity=0)

    assert list(list_user_collection_items(user, owned=True)) == [held]
    assert list(list_user_collection_items(user, owned=False)) == [not_held]


@pytest.mark.django_db
def test_구함_필터_False는_구함이_아닌_항목만_반환한다(make_user):
    """`is_wanted=False`는 quantity와 무관하게 is_wanted가 False인 행을 선택한다
    — "보유"와는 다르다(보유/구함은 독립된 축, 계획서 §D1). quantity>0이면서
    is_wanted=True인 행은 "보유"이기도 하지만 is_wanted=False 결과에서는
    제외돼야 한다. 이는 예전에 웹 /collection/?is_wanted=false로 접근하던
    동작(지금은 레거시 북마크 호환을 위해 ?owned=true로 리다이렉트)의 쿼리
    계층 가드다 — API 호출자는 /api/collection-items/에서 여전히
    is_wanted=false를 그대로 쓴다."""
    user = make_user(username="ci-query-is-wanted-false")
    not_wanted = CollectionItem.objects.create(user=user, name="보유", quantity=3, is_wanted=False)
    owned_and_wanted = CollectionItem.objects.create(
        user=user, name="보유하며구함", quantity=2, is_wanted=True
    )

    assert list(list_user_collection_items(user, is_wanted=False)) == [not_wanted]
    assert owned_and_wanted not in list(list_user_collection_items(user, is_wanted=False))


@pytest.mark.django_db
def test_통합검색어는_이름_작품명_캐릭터명_메모에서_일치하되_상품유형은_대상에서_제외한다(
    make_user,
):
    """`q`는 name/work_title/character_name/memo를 icontains로 좁힌다 —
    list_user_personal_entries의 q 패턴과 동일. item_type은 의도적으로 검색
    대상이 아니며, item_type에만 일치하는 미끼 행은 제외돼야 한다."""
    user = make_user(username="ci-query-q")
    other = make_user(username="ci-query-q-other")
    by_name = CollectionItem.objects.create(user=user, name="레어 스탬프")
    by_work_title = CollectionItem.objects.create(
        user=user, name="굿즈 1", work_title="레어 작품"
    )
    by_character_name = CollectionItem.objects.create(
        user=user, name="굿즈 2", character_name="레어 캐릭터"
    )
    by_memo = CollectionItem.objects.create(user=user, name="굿즈 3", memo="레어 메모")
    item_type_decoy = CollectionItem.objects.create(
        user=user, name="굿즈 4", item_type="레어 타입"
    )
    other_user_same_name = CollectionItem.objects.create(user=other, name="레어 스탬프")

    items = set(list_user_collection_items(user, q="레어"))

    assert items == {by_name, by_work_title, by_character_name, by_memo}
    assert item_type_decoy not in items
    assert other_user_same_name not in items


@pytest.mark.django_db
def test_빈_통합검색어는_아무_항목도_걸러내지_않는다(make_user):
    """빈 `q`는 아무것도 걸러내면 안 된다.

    `if q:`는 정확성 가드가 아니라 쿼리 최적화다: Django는
    `Q(field__icontains="")`를 `field LIKE '%%'`로 렌더링해 필드값과 무관하게
    모든 행에 매치되므로, `if q is not None:`으로 바꿔도 동작은 동일하고 이
    테스트도 여전히 통과해야 한다 — 이 가드는 빈 문자열의 과잉 필터링을 막는
    게 아니라 no-op인 icontains 절 4개를 건너뛰기 위한 것이다.

    검색 대상 네 필드 모두를 빈 기본값이 아닌 서로 다른 값으로 채운 이유는,
    진짜로 깨진 조회(예: 가드를 없앤 채 `icontains`를 `exact`로 바꾼 경우)가
    필드가 우연히 비어 있는 행에서만 우연히 일치해 통과해버리는 일을 막기
    위해서다.
    """
    user = make_user(username="ci-query-q-empty")
    first = CollectionItem.objects.create(
        user=user,
        name="굿즈 1",
        work_title="작품 1",
        character_name="캐릭터 1",
        memo="메모 1",
    )
    second = CollectionItem.objects.create(
        user=user,
        name="굿즈 2",
        work_title="작품 2",
        character_name="캐릭터 2",
        memo="메모 2",
    )

    items = set(list_user_collection_items(user, q=""))

    assert items == {first, second}


# ---------------------------------------------------------------------------
# user_collection_item_filter_values (PR-C5b-1). user_visit_category_values는
# 호출자가 core.vocab 라벨을 해석한 뒤 중복 제거하지만(archive/queries.py는
# core.vocab을 임포트하지 않는다), work_title/character_name/item_type은
# vocab 해석 단계가 없는 자유 텍스트라서 중복 제거와 공백 제외를 뷰가 아니라
# 이 쿼리 계층에서 직접 처리한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_필터_선택지_조회는_소유자로_범위를_좁히고_중복값을_제거한다(make_user):
    user = make_user(username="ci-filter-values-user")
    other = make_user(username="ci-filter-values-other")
    CollectionItem.objects.create(user=user, name="굿즈 1", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="굿즈 2", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="굿즈 3", character_name="캐릭터 A")
    CollectionItem.objects.create(user=user, name="굿즈 4", character_name="캐릭터 A")
    CollectionItem.objects.create(user=user, name="굿즈 5", item_type="스탬프")
    CollectionItem.objects.create(user=user, name="굿즈 6", item_type="스탬프")
    CollectionItem.objects.create(
        user=other, name="남의 굿즈", work_title="작품 A", character_name="캐릭터 A", item_type="스탬프"
    )

    values = user_collection_item_filter_values(user)

    assert values == {
        "work_title": ["작품 A"],
        "character_name": ["캐릭터 A"],
        "item_type": ["스탬프"],
    }


@pytest.mark.django_db
def test_필터_선택지_목록은_정렬된_순서로_반환된다(make_user):
    """각 목록은 정렬돼 있어야 한다 — C5b-2가 이 값을 그대로 <select> 옵션으로
    렌더한다.

    이 테스트는 계약을 문서화할 뿐 회귀를 막지는 못한다. 마이그레이션 0019의
    (user, work_title) 복합 인덱스 덕분에 이 테이블 크기에서는 `.order_by()`를
    지워도 Postgres 플래너가 이미 정렬된 행을 돌려줘 테스트가 실패하지 않는다
    (실제로 지우고 재실행해 확인함). `.order_by()`가 필요한 근거는 ORDER BY
    없는 DISTINCT의 순서가 일반적으로 미정의라는 데 있다(예: 행 수나 통계가
    바뀌면 플래너가 다른 HashAggregate 계획을 고를 수 있음) — 플래너를
    인덱스 기반 계획에서 강제로 벗어나게 해(`SET enable_indexscan/enable_sort
    = off` 등) 실제로 정렬되지 않은 출력을 확인해 검증했다. 이 강제 플래너
    확인은 이 저장소가 아니라 Postgres 플래너를 테스트하는 셈이라 자동
    테스트로는 반복하지 않는다.
    """
    user = make_user(username="ci-filter-values-order")
    CollectionItem.objects.create(user=user, name="굿즈 1", work_title="작품 C")
    CollectionItem.objects.create(user=user, name="굿즈 2", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="굿즈 3", work_title="작품 B")

    values = user_collection_item_filter_values(user)

    assert values["work_title"] == ["작품 A", "작품 B", "작품 C"]


@pytest.mark.django_db
def test_값이_비어있는_필드는_필터_선택지_목록에_포함되지_않는다(make_user):
    user = make_user(username="ci-filter-values-blank")
    CollectionItem.objects.create(
        user=user,
        name="굿즈 1",
        work_title="작품 B",
        character_name="캐릭터 B",
        item_type="피규어",
    )
    CollectionItem.objects.create(user=user, name="굿즈 2")

    values = user_collection_item_filter_values(user)

    assert values == {
        "work_title": ["작품 B"],
        "character_name": ["캐릭터 B"],
        "item_type": ["피규어"],
    }


@pytest.mark.django_db
def test_컬렉션_아이템이_없는_사용자의_필터_선택지는_모두_빈_목록이다(make_user):
    user = make_user(username="ci-filter-values-empty")

    values = user_collection_item_filter_values(user)

    assert values == {"work_title": [], "character_name": [], "item_type": []}


# ---------------------------------------------------------------------------
# user_collection_item_summary_counts (PR-C5b-1, 컬렉션 3축 독립화 트랙에서
# 개정, 2026-07-28). owned/wanted/tradeable은 분할이 아니라 서로 독립된
# 세 축이다(계획서 §D1, .docs/plans/2026-07-15-collection-domain-design-plan.md:55,
# "wanted와 보유 공존 허용") — 한 행이 owned이면서 동시에 wanted일 수 있어
# owned_count + wanted_count가 전체 개수가 아니다. total_count가 따로
# 존재하는 이유다. 웹의 구함 칩은 여전히 ?is_wanted=true를 쓰지만, 옛 보유
# 칩 URL(?is_wanted=false)은 이제 ?owned=true로 302 리다이렉트된다(레거시
# 북마크 호환). DRF API는 ?is_wanted=false를 원래 의미 그대로 유지한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_보유_구함_집계는_수량_합계가_아니라_행_개수를_센다(make_user):
    user = make_user(username="ci-summary-counts-user")
    other = make_user(username="ci-summary-counts-other")
    CollectionItem.objects.create(user=user, name="보유 굿즈", quantity=5, is_wanted=False)
    CollectionItem.objects.create(user=user, name="구함 굿즈 1", quantity=0, is_wanted=True)
    CollectionItem.objects.create(user=user, name="구함 굿즈 2", quantity=0, is_wanted=True)
    CollectionItem.objects.create(user=other, name="남의 굿즈", quantity=9, is_wanted=False)

    counts = user_collection_item_summary_counts(user)

    assert counts == {
        "owned_count": 1,
        "wanted_count": 2,
        "tradeable_count": 0,
        "total_count": 3,
    }


@pytest.mark.django_db
def test_컬렉션_아이템이_없는_사용자의_보유_구함_집계는_0이다(make_user):
    user = make_user(username="ci-summary-counts-empty")

    counts = user_collection_item_summary_counts(user)

    assert counts == {
        "owned_count": 0,
        "wanted_count": 0,
        "tradeable_count": 0,
        "total_count": 0,
    }


@pytest.mark.django_db
def test_보유_구함_교환희망_세_축은_서로_독립적으로_집계된다(make_user):
    """owned/wanted/tradeable은 상호 배타적 분할이 아니라 서로 독립된 세 축이다
    (계획서 §D1, .docs/plans/2026-07-15-collection-domain-design-plan.md:55,
    "wanted와 보유 공존 허용" — quantity>0, is_wanted=True, tradeable_quantity>0이
    한 행에서 임의로 조합될 수 있다). 한 행이 여러 축에 동시에 집계될 수 있다."""
    user = make_user(username="ci-summary-counts-axes")
    CollectionItem.objects.create(
        user=user, name="품목1", quantity=3, is_wanted=False, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="품목2", quantity=0, is_wanted=True, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="품목3", quantity=2, is_wanted=True, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="품목4", quantity=4, is_wanted=False, tradeable_quantity=2
    )
    CollectionItem.objects.create(
        user=user, name="품목5", quantity=3, is_wanted=True, tradeable_quantity=2
    )

    counts = user_collection_item_summary_counts(user)

    assert counts["owned_count"] == 4
    assert counts["wanted_count"] == 3
    assert counts["tradeable_count"] == 2


@pytest.mark.django_db
def test_전체_집계는_보유_구함_카운트의_단순_합과_다르다(make_user):
    """total_count는 축 소속과 무관하게 사용자가 가진 모든 행(존재 자체)을
    센다. owned_count + wanted_count로 유도할 수 없다 — 계획서 §D1
    (.docs/plans/2026-07-15-collection-domain-design-plan.md:55, "wanted와
    보유 공존 허용")에 따라 한 행이 여러 축에 중복 집계될 수 있으므로, 축별
    카운트로는 전체 재고 총량을 대신할 수 없다."""
    user = make_user(username="ci-summary-counts-total")
    other = make_user(username="ci-summary-counts-total-other")
    CollectionItem.objects.create(
        user=user, name="줄1", quantity=3, is_wanted=False, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="줄2", quantity=0, is_wanted=True, tradeable_quantity=0
    )
    CollectionItem.objects.create(
        user=user, name="줄3", quantity=0, is_wanted=False, tradeable_quantity=0
    )
    CollectionItem.objects.create(user=other, name="타인의 줄", quantity=1, is_wanted=False)

    counts = user_collection_item_summary_counts(user)

    assert counts["total_count"] == 3
    assert counts["owned_count"] + counts["wanted_count"] == 2
    assert counts["owned_count"] + counts["wanted_count"] != counts["total_count"]


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


# ---------------------------------------------------------------------------
# user_collection_item_summary_counts — tradeable_count (컬렉션 리디자인
# 백엔드). tradeable_count는 owned/wanted 옆의 세 번째 분할이 아니라 겹치는
# 파생 축이다 — tradeable_quantity>0인 보유 아이템은 owned_count와
# tradeable_count 양쪽에 동시에 집계돼야 한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_요약_집계는_교환가능_수량이_1개_이상인_항목_개수를_tradeable_count로_반환한다(make_user):
    user = make_user(username="ci-summary-tradeable")
    CollectionItem.objects.create(
        user=user, name="교환 가능 1", quantity=2, tradeable_quantity=1
    )
    CollectionItem.objects.create(
        user=user, name="교환 가능 2", quantity=3, tradeable_quantity=2
    )
    CollectionItem.objects.create(
        user=user, name="교환 불가", quantity=3, tradeable_quantity=0
    )

    counts = user_collection_item_summary_counts(user)

    assert counts["tradeable_count"] == 2


@pytest.mark.django_db
def test_교환가능_집계는_보유_구함_분할과_겹치는_축이라_보유_항목이_교환가능이면_양쪽_모두_집계된다(make_user):
    """tradeable_count는 상호 배타 분할이 아니다 — is_wanted=False인 보유
    아이템도 tradeable_quantity>0이면 owned_count와 tradeable_count 양쪽에
    동시에 집계된다(owned/wanted처럼 배타적으로 나뉘지 않고 의도적으로
    겹친다)."""
    user = make_user(username="ci-summary-tradeable-overlap")
    CollectionItem.objects.create(
        user=user,
        name="보유하며_교환가능",
        is_wanted=False,
        quantity=2,
        tradeable_quantity=1,
    )

    counts = user_collection_item_summary_counts(user)

    assert counts["owned_count"] == 1
    assert counts["tradeable_count"] == 1


# ---------------------------------------------------------------------------
# user_collection_item_work_title_facets (컬렉션 리디자인 백엔드,
# 작품별 색상 인덱스/필터 근거 집계). work_title이 비어있는 행은 제외하고,
# count 내림차순·동수는 work_title 오름차순으로 정렬하며 소유자로 범위를
# 좁힌다.
# 각 facet 은 {"work_title", "count", "first_id"} dict 이며 first_id 는
# 그 작품의 최초 등록(가장 작은 id) 아이템의 id 다 — 순번 기반 색 배정의
# 근거가 되는 필드라 해시 대체(색 배정을 순번으로 바꾸는 이번 변경)의 핵심.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_작품명별_항목_facet_집계는_작품명이_비어있는_항목을_제외한다(make_user):
    user = make_user(username="ci-work-title-counts-blank")
    item = CollectionItem.objects.create(user=user, name="굿즈 1", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="굿즈 2")

    facets = user_collection_item_work_title_facets(user)

    assert facets == [{"work_title": "작품 A", "count": 1, "first_id": item.id}]


@pytest.mark.django_db
def test_작품명별_항목_facet_집계는_개수_내림차순_동수는_작품명_오름차순으로_정렬된다(make_user):
    user = make_user(username="ci-work-title-counts-order")
    # 작품 C: 1건, 작품 A: 2건, 작품 B: 2건 (A/B는 개수가 같아 동수 정렬 케이스)
    c1 = CollectionItem.objects.create(user=user, name="C1", work_title="작품 C")
    a1 = CollectionItem.objects.create(user=user, name="A1", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="A2", work_title="작품 A")
    b1 = CollectionItem.objects.create(user=user, name="B1", work_title="작품 B")
    CollectionItem.objects.create(user=user, name="B2", work_title="작품 B")

    facets = user_collection_item_work_title_facets(user)

    assert facets == [
        {"work_title": "작품 A", "count": 2, "first_id": a1.id},
        {"work_title": "작품 B", "count": 2, "first_id": b1.id},
        {"work_title": "작품 C", "count": 1, "first_id": c1.id},
    ]


@pytest.mark.django_db
def test_작품명별_항목_facet_집계는_소유자로_범위를_좁힌다(make_user):
    user = make_user(username="ci-work-title-counts-owner")
    other = make_user(username="ci-work-title-counts-other")
    item = CollectionItem.objects.create(user=user, name="내 굿즈", work_title="작품 A")
    CollectionItem.objects.create(user=other, name="남의 굿즈", work_title="작품 A")

    facets = user_collection_item_work_title_facets(user)

    assert facets == [{"work_title": "작품 A", "count": 1, "first_id": item.id}]


@pytest.mark.django_db
def test_작품명별_항목_facet_집계의_first_id는_그_작품의_최초_등록_아이템_id다(make_user):
    user = make_user(username="ci-work-title-counts-first-id")
    first = CollectionItem.objects.create(user=user, name="첫번째", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="두번째", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="세번째", work_title="작품 A")

    facets = user_collection_item_work_title_facets(user)

    assert facets == [{"work_title": "작품 A", "count": 3, "first_id": first.id}]


# ---------------------------------------------------------------------------
# user_visit_record_photo_count (AS-1/AS-2, account-settings-editorial 계획서
# — 계정 탈퇴 화면의 "기록 사진" 카운트가 이 함수를 쓴다)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문기록_사진_카운트는_본인_소유_방문기록의_사진만_집계한다(
    make_user, make_event, make_visit, make_visit_photo
):
    """두 사용자가 각자 자신의 VisitRecord를 갖도록 만든다 — 같은
    visit_record를 공유하면 소유자 범위 분리가 전혀 검증되지 않는다
    (계획서 픽스처 함정 2번)."""
    user = make_user(username="photo-count-owner")
    other = make_user(username="photo-count-other")
    my_visit = make_visit(user, event=make_event(title="내 방문"), visited_on="2026-01-01")
    other_visit = make_visit(other, event=make_event(title="남의 방문"), visited_on="2026-01-02")

    make_visit_photo(my_visit)
    make_visit_photo(my_visit)
    make_visit_photo(other_visit)

    assert user_visit_record_photo_count(user) == 2


@pytest.mark.django_db
def test_방문기록_사진이_없는_사용자의_사진_카운트는_0이다(make_user):
    user = make_user(username="photo-count-empty")

    assert user_visit_record_photo_count(user) == 0
