"""Date-jump search read layer (활동 달력 에디토리얼 계획 §4-a-1/B6).

archive.queries.find_latest_activity_date_for_query does not exist yet — the
whole file is expected to fail at collection with ImportError until it is
added (mirrors test_activity_calendar_queries.py's own documented convention
for a not-yet-existing query function).

Scope: this file covers only the read-side matching/date-selection contract
(the pure query function). The view-level PRG-redirect/no-match/month-
preservation contract lives in tests/core/test_activity_calendar_view.py,
which is this function's only caller.

These scenarios build state directly on the models (not via archive.services)
— the same convention test_activity_calendar_queries.py already documents for
this read layer.
"""
from datetime import date

import pytest

from archive.models import CollectionItem
from archive.queries import GOODS_ACQUIRED_KIND, SCHEDULE_KIND, find_latest_activity_date_for_query

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_라벨에_검색어가_포함된_항목의_날짜를_반환한다(make_user):
    user = make_user()
    CollectionItem.objects.create(
        user=user, name="검색점프도메인굿즈", acquired_on=date(2026, 7, 10)
    )

    result = find_latest_activity_date_for_query(user, "검색점프도메인")

    assert result == date(2026, 7, 10)


@pytest.mark.django_db
def test_여러_건_일치하면_가장_최근_날짜를_반환한다(make_user):
    user = make_user()
    CollectionItem.objects.create(
        user=user, name="다중일치검색굿즈오래됨", acquired_on=date(2026, 1, 5)
    )
    CollectionItem.objects.create(
        user=user, name="다중일치검색굿즈최근", acquired_on=date(2026, 7, 20)
    )

    result = find_latest_activity_date_for_query(user, "다중일치검색")

    assert result == date(2026, 7, 20)


@pytest.mark.django_db
def test_일치하는_항목이_없으면_None을_반환한다(make_user):
    user = make_user()
    CollectionItem.objects.create(
        user=user, name="검색무일치용다른이름아이템", acquired_on=date(2026, 7, 10)
    )

    result = find_latest_activity_date_for_query(user, "존재하지않는검색어")

    assert result is None


@pytest.mark.django_db
def test_kinds로_좁히면_해당_종류가_아닌_일치는_찾지_않는다(make_user, make_event, make_status):
    user = make_user()
    scheduled_event = make_event(
        title="검색종류필터일정매치행사", start_date=date(2026, 7, 3), end_date=date(2026, 7, 5)
    )
    make_status(user, scheduled_event)

    scoped_to_goods_only = find_latest_activity_date_for_query(
        user, "검색종류필터일정매치", kinds=[GOODS_ACQUIRED_KIND]
    )
    scoped_to_schedule = find_latest_activity_date_for_query(
        user, "검색종류필터일정매치", kinds=[SCHEDULE_KIND]
    )

    assert scoped_to_goods_only is None
    assert scoped_to_schedule == date(2026, 7, 3)


@pytest.mark.django_db
def test_검색어_대소문자를_구분하지_않는다(make_user):
    user = make_user()
    CollectionItem.objects.create(
        user=user, name="SearchCaseSensitivityTest", acquired_on=date(2026, 7, 10)
    )

    result = find_latest_activity_date_for_query(user, "searchcasesensitivitytest")

    assert result == date(2026, 7, 10)


@pytest.mark.django_db
def test_다른_사용자의_활동은_검색되지_않는다(make_user):
    user = make_user()
    other_user = make_user(username="search-jump-other-user")
    CollectionItem.objects.create(
        user=other_user, name="타인검색점프굿즈", acquired_on=date(2026, 7, 10)
    )

    result = find_latest_activity_date_for_query(user, "타인검색점프")

    assert result is None


@pytest.mark.django_db
@pytest.mark.parametrize("blank_q", ["", "   "], ids=["빈_문자열", "공백만"])
def test_빈_검색어는_None을_반환한다(make_user, blank_q):
    user = make_user()
    CollectionItem.objects.create(
        user=user, name="빈검색어굿즈", acquired_on=date(2026, 7, 10)
    )

    result = find_latest_activity_date_for_query(user, blank_q)

    assert result is None
