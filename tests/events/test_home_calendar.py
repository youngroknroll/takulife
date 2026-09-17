"""홈 히어로 아래 이벤트 달력 섹션 컨텍스트 계약을 검증한다(트랙 34).

다루는 범위: 파라미터 없는 기본 진입 시 이번 달·오늘 선택.
"""
import pytest
from datetime import date
from unittest.mock import patch

from django.test import Client

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_파라미터_없이_홈을_열면_컨텍스트에_이번_달과_오늘이_기본으로_담긴다():
    today = date(2026, 9, 16)
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/")

    calendar = resp.context["home_calendar"]
    assert calendar["year"] == 2026
    assert calendar["month"] == 9
    assert calendar["selected_date"] == date(2026, 9, 16)


@pytest.mark.django_db
def test_파라미터_없이_홈을_열면_오늘_칸에_오늘과_선택_플래그가_모두_참으로_담긴다():
    today = date(2026, 9, 16)
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/")

    calendar = resp.context["home_calendar"]
    assert all(len(week) == 7 for week in calendar["weeks"])
    assert calendar["month_param"] == "2026-09"
    assert calendar["selected_is_today"] is True

    today_cells = [
        day
        for week in calendar["weeks"]
        for day in week
        if day["date"] == date(2026, 9, 16)
    ]
    assert len(today_cells) == 1
    assert today_cells[0]["today"] is True
    assert today_cells[0]["selected"] is True


@pytest.mark.django_db
def test_month_파라미터로_다른_달을_열면_그_달_1일이_선택된다():
    today = date(2026, 9, 16)
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/", {"month": "2026-11"})

    calendar = resp.context["home_calendar"]
    assert calendar["year"] == 2026
    assert calendar["month"] == 11
    assert calendar["selected_date"] == date(2026, 11, 1)
    assert calendar["selected_is_today"] is False

    in_month_dates = {
        day["date"]
        for week in calendar["weeks"]
        for day in week
        if day["in_month"]
    }
    assert date(2026, 11, 1) in in_month_dates
    assert date(2026, 11, 30) in in_month_dates


@pytest.mark.django_db
@pytest.mark.parametrize(
    "params",
    [{"month": "2026-09", "date": "2026-09-20"}, {"date": "2026-09-20"}],
    ids=["월과_함께", "날짜만"],
)
def test_date_파라미터로_날짜를_지정하면_그_날짜가_선택된다(params):
    today = date(2026, 9, 16)
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/", params)

    calendar = resp.context["home_calendar"]
    assert calendar["selected_date"] == date(2026, 9, 20)

    selected_cells = [
        day
        for week in calendar["weeks"]
        for day in week
        if day["date"] == date(2026, 9, 20)
    ]
    assert len(selected_cells) == 1
    assert selected_cells[0]["selected"] is True

    today_cells = [
        day
        for week in calendar["weeks"]
        for day in week
        if day["date"] == date(2026, 9, 16)
    ]
    assert len(today_cells) == 1
    assert today_cells[0]["selected"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "params",
    [{"month": "2026-13"}, {"month": "2026-10", "date": "2026-09-20"}],
    ids=["잘못된_월_형식", "표시_월_밖_날짜"],
)
def test_잘못된_month_또는_date_값은_오류_없이_이번_달_오늘로_되돌아간다(params):
    today = date(2026, 9, 16)
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/", params)

    assert resp.status_code == 200
    calendar = resp.context["home_calendar"]
    assert calendar["year"] == 2026
    assert calendar["month"] == 9
    assert calendar["selected_date"] == date(2026, 9, 16)
    assert "요청한 날짜를 확인할 수 없어요" not in resp.content.decode()


@pytest.mark.django_db
def test_이전_다음_달_값은_연도_경계를_넘어간다():
    today = date(2026, 9, 16)
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/", {"month": "2026-12"})

    calendar = resp.context["home_calendar"]
    assert calendar["prev_month"] == "2026-11"
    assert calendar["next_month"] == "2027-01"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("end_date", "expected_counts"),
    [
        (date(2026, 9, 12), {10: 1, 11: 1, 12: 1, 13: 0}),
        (None, {10: 1, 11: 0}),
    ],
    ids=["종료일_있음", "종료일_없음"],
)
def test_기간_행사는_시작일부터_종료일까지_날짜_칸에_반영되고_종료일이_없으면_시작일만_반영된다(
    make_event, end_date, expected_counts
):
    today = date(2026, 9, 16)
    make_event(
        title="기간 행사",
        category="popup_store",
        start_date=date(2026, 9, 10),
        end_date=end_date,
    )
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/")

    calendar = resp.context["home_calendar"]
    cells = {
        day["date"]: day
        for week in calendar["weeks"]
        for day in week
        if day["in_month"]
    }
    for day, expected_count in expected_counts.items():
        cell = cells[date(2026, 9, day)]
        assert cell["count"] == expected_count
        if expected_count == 1:
            assert cell["categories"] == ["popup_store"]
        else:
            assert cell["categories"] == []
