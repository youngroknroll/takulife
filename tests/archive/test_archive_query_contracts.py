"""Query-count contracts for archive/queries.py.

Kept out of test_archive_queries.py: that module sets a file-wide
``pytestmark = pytest.mark.domain``, which would swallow the ``contract``
marker on tests placed here. Precedent: tests/staff/test_staff_queries.py and
tests/core/test_analytics_recording_resilience.py both use a bare
``@pytest.mark.contract`` on individual tests instead of a module-wide marker.
"""
import pytest

from archive.queries import list_user_statuses


@pytest.mark.contract
@pytest.mark.django_db
def test_상태_목록_조회는_리뷰_주석이_추가돼도_쿼리_수가_늘지_않는다(
    make_user, make_event, make_entry, make_status, make_visit, django_assert_num_queries
):
    """Regression guard, not a Red→Green cycle — list_user_statuses' review
    annotation (visit_record_id / review_text via a correlated Subquery) and
    its select_related("event", "personal_entry") are already implemented,
    so this test is expected to pass immediately.

    This contract covers *two* things a mutation test must both catch:
    1. The correlated visit-record Subquery must not re-execute per row.
    2. Reading the row's subject (event.title / personal_entry.title —
       exactly what the real _subject_view template path reads) must not
       cost a query per row either (the select_related guard).

    An earlier version of this test only accessed the annotated scalars
    (review_text, visit_record_id) and never dereferenced row.event or
    row.personal_entry — removing select_related("event", "personal_entry")
    from the implementation still passed, because annotated scalars don't
    traverse the FK. This version was hardened after that mutation-test gap
    was found: the loop below now also reads event.title /
    personal_entry.title so a removed select_related is caught (N+1).

    N=1 was measured on the current implementation before this test was
    written (not picked arbitrarily first, then to make the implementation
    fit): select_related covers both subject FKs and both Subquery
    annotations are inlined into the same SELECT, so listing 3 rows — one
    event subject with a reviewed visit, one event subject with an
    unreviewed visit, one personal_entry subject with no visit at all —
    still costs exactly one query, whether or not a row has a visit record.
    If this ever grows past 1, either the correlated visit-record subquery
    started re-executing per row, or a subject FK started being fetched
    lazily per row instead of via select_related.
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
