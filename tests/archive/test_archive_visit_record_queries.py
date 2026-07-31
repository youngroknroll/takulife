"""아카이브 읽기 계층(archive/queries.py) 단위 테스트 — 방문 기록(VisitRecord) 조회.

list_user_visit_records/list_items_acquired_at_visit/
list_visit_records_for_personal_entry/user_visit_record_counts를 검증한다.
"""

import pytest

from archive.models import PersonalEntry, VisitRecord
from archive.queries import (
    list_items_acquired_at_visit,
    list_user_visit_records,
    list_visit_records_for_personal_entry,
    user_visit_record_counts,
)

pytestmark = pytest.mark.domain


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
