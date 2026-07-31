"""날짜 점프 검색 읽기 계층 (활동 달력 에디토리얼 계획 §4-a-1/B6).

archive.queries.find_latest_activity_date_for_query가 아직 없어 이 파일은
ImportError로 수집 실패하는 게 정상이다(test_activity_calendar_queries.py와
동일한 관례).

범위: 이 파일은 읽기 쪽 매칭/날짜 선택 계약(순수 쿼리 함수)만 다룬다.
뷰 레벨 PRG 리다이렉트/무매칭/월 유지 계약은 이 함수의 유일한 호출자인
tests/core/test_activity_calendar_view.py에 있다.

이 시나리오들은 archive.services를 거치지 않고 모델에 직접 상태를 만든다
— test_activity_calendar_queries.py가 이미 문서화한 이 읽기 계층의 관례와 같다.
"""
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

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


# ---------------------------------------------------------------------------
# 활동 달력 백로그 #2 — 날짜 점프 검색은 label 매칭을 DB로 내려야 한다
# (전체 이력 무제한 범위를 파이썬 레벨 casefold 비교로 훑는 풀스캔 금지).
# 이 계약은 쿼리 "개수"만으로는 검증되지 않는다 — 기존(결함이 있는) 구현도
# 소스별 1쿼리씩 실행하지만 그 쿼리에 이름/라벨 조건이 전혀 없어 사용자의
# 전체 데이터를 그대로 가져와 파이썬에서 걸렀다. 그래서 실행된 SQL 자체에
# 검색어가 WHERE절로 내려갔는지를 직접 확인한다.
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
def test_검색어가_DB_쿼리의_WHERE절로_내려가_전체_이력을_파이썬으로_훑지_않는다(
    make_user,
):
    user = make_user()
    CollectionItem.objects.create(
        user=user, name="쿼리하향검색굿즈", acquired_on=date(2026, 7, 10)
    )
    for i in range(30):
        CollectionItem.objects.create(
            user=user, name=f"쿼리하향무관굿즈{i}", acquired_on=date(2020, 1, 1)
        )

    with CaptureQueriesContext(connection) as ctx:
        result = find_latest_activity_date_for_query(user, "쿼리하향검색")

    assert result == date(2026, 7, 10)
    assert any(
        "쿼리하향검색" in query["sql"] for query in ctx.captured_queries
    ), "검색어가 DB 쿼리 WHERE절로 내려가지 않음 — 파이썬 레벨 전체 스캔 의심"
