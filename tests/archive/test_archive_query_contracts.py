"""archive/queries.py의 쿼리 수 계약 테스트.

tests/archive/test_archive_*_queries.py에 두지 않은 이유: 그 모듈들은 파일 전체에
``pytestmark = pytest.mark.domain``을 설정하므로, 여기 둔 테스트의 ``contract``
마커가 묻혀버린다. tests/staff/test_staff_queries.py,
tests/core/test_analytics_recording_resilience.py도 같은 이유로 모듈 전체
마커 대신 개별 테스트에 ``@pytest.mark.contract``를 붙인다.
"""
import pytest

from archive.queries import list_user_statuses


@pytest.mark.contract
@pytest.mark.django_db
def test_상태_목록_조회는_리뷰_주석이_추가돼도_쿼리_수가_늘지_않는다(
    make_user, make_event, make_entry, make_status, make_visit, django_assert_num_queries
):
    """Red→Green이 아니라 회귀 가드다 — list_user_statuses의 리뷰 주석
    (Subquery 기반 visit_record_id / review_text)과
    select_related("event", "personal_entry")는 이미 구현되어 있어 이 테스트는
    작성 시점에 곧바로 통과한다.

    뮤테이션 테스트가 둘 다 잡아내야 하는 두 가지를 함께 검증한다:
    1. 상관 서브쿼리(visit-record Subquery)가 행마다 재실행되지 않아야 한다.
    2. 각 행의 대상(event.title / personal_entry.title — 실제
       _subject_view 템플릿이 읽는 값과 동일)을 읽는 것도 행마다 쿼리를
       추가로 쓰지 않아야 한다(select_related 가드).

    이전 버전은 주석된 스칼라(review_text, visit_record_id)만 접근하고
    row.event/row.personal_entry를 역참조하지 않아, select_related를
    제거해도 통과했다(스칼라 주석은 FK를 타지 않으므로). 이 간극을 뮤테이션
    테스트로 발견한 뒤, 아래 루프에서 event.title / personal_entry.title도
    읽도록 강화해 select_related 제거(N+1)를 잡아내게 했다.

    N=1은 이 테스트를 쓰기 전에 현재 구현으로 실측한 값이다(구현에 맞춰
    임의로 정한 게 아니다): select_related가 두 대상 FK를 모두 커버하고
    두 Subquery 주석이 같은 SELECT에 인라인되므로, 리뷰 있는 방문·리뷰
    없는 방문·방문 기록 없음 세 행을 나열해도 방문 기록 유무와 무관하게
    쿼리 1회로 끝난다. 이 값이 1을 넘으면 상관 서브쿼리가 행마다
    재실행되기 시작했거나, 대상 FK가 select_related 없이 지연 로딩되기
    시작한 것이다.
    """
    user = make_user()
    event_with_review = make_event(title="리뷰 있음")
    event_with_visit_no_review = make_event(title="리뷰 없는 방문")
    entry_without_visit = make_entry(user, title="방문 기록 없음")

    make_status(user, event=event_with_review, status="visited")
    make_status(user, event=event_with_visit_no_review, status="visited")
    make_status(user, personal_entry=entry_without_visit, status="planned")

    make_visit(
        user,
        event=event_with_review,
        visited_on="2026-01-01",
        short_review="다녀왔어요",
    )
    make_visit(
        user,
        event=event_with_visit_no_review,
        visited_on="2026-01-02",
    )

    with django_assert_num_queries(1):
        rows = list(list_user_statuses(user))
        for row in rows:
            row.review_text
            row.visit_record_id
            if row.event_id:
                row.event.title
            if row.personal_entry_id:
                row.personal_entry.title
