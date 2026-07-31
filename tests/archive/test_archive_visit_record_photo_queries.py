"""아카이브 읽기 계층(archive/queries.py) 단위 테스트 — 방문 기록 사진 카운트 조회.

user_visit_record_photo_count를 검증한다.
"""

import pytest

from archive.queries import user_visit_record_photo_count

pytestmark = pytest.mark.domain


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
