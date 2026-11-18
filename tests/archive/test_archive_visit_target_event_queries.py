"""아카이브 읽기 계층(archive/queries.py) 단위 테스트 — 방문 기록 대상 행사.

list_user_visit_target_events를 검증한다.
"""

import pytest

from archive.queries import list_user_visit_target_events

pytestmark = pytest.mark.domain


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("is_published", "own_status", "other_status", "expected"),
    [
        pytest.param(True, None, None, True, id="게시_행사_상태_없음"),
        pytest.param(False, "visited", None, True, id="비공개_본인_방문_완료"),
        pytest.param(False, None, None, False, id="비공개_상태_없음"),
        pytest.param(False, "planned", None, False, id="비공개_본인_예정"),
        pytest.param(False, "missed", None, False, id="비공개_본인_불참"),
        pytest.param(False, None, "visited", False, id="비공개_타인_방문_완료만"),
        pytest.param(False, "planned", "visited", False, id="비공개_본인_예정_타인_방문_완료"),
    ],
)
def test_방문_기록_대상_행사_목록은_게시된_행사와_본인이_방문_완료로_표시한_행사만_포함한다(
    make_user,
    make_event,
    make_draft_event,
    make_status,
    is_published,
    own_status,
    other_status,
    expected,
):
    user = make_user(username="visit-target-user")
    other = make_user(username="visit-target-other")
    event = make_event() if is_published else make_draft_event()
    if own_status is not None:
        make_status(user, event=event, status=own_status)
    if other_status is not None:
        make_status(other, event=event, status=other_status)

    events = list(list_user_visit_target_events(user))

    assert (event in events) is expected


@pytest.mark.django_db
def test_방문_기록_대상_행사_목록은_여러_사용자가_방문_완료로_표시한_게시_행사도_한_번만_반환한다(
    make_user, make_event, make_status
):
    user = make_user(username="visit-target-user")
    event = make_event()
    for visitor in (user, make_user(username="visitor-a"), make_user(username="visitor-b")):
        make_status(visitor, event=event, status="visited")

    assert list(list_user_visit_target_events(user)) == [event]
