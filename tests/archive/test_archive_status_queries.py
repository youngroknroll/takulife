"""아카이브 읽기 계층(archive/queries.py) 단위 테스트 — 상태(UserEventStatus) 조회.

user_status_counts/list_user_statuses/list_user_unrecorded_visited_statuses와
ARCHIVE_STATUS_SLUGS를 검증한다.
"""

from datetime import datetime

import pytest
from django.utils import timezone

from archive.models import UserEventStatus
from archive.queries import (
    ARCHIVE_STATUS_SLUGS,
    list_user_statuses,
    list_user_unrecorded_visited_statuses,
    user_status_counts,
)

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
