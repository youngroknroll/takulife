"""홈 히어로 아래 이벤트 달력 섹션 컨텍스트 계약을 검증한다(트랙 34).

다루는 범위: 파라미터 없는 기본 진입 시 이번 달·오늘 선택.
"""
import html
import re

import pytest
from datetime import date
from unittest.mock import patch

from django.test import Client

pytestmark = pytest.mark.web


def _find_href(body, link_text):
    match = re.search(
        rf'<a[^>]*href="([^"]*)"[^>]*>\s*{re.escape(link_text)}\s*</a>', body
    )
    if not match:
        return None
    return html.unescape(match.group(1))


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


@pytest.mark.unit
def test_같은_카테고리가_중복이면_하나로_합쳐진다():
    from web.views.events import _dedupe_category_slugs

    assert _dedupe_category_slugs(["popup_store", "popup_store"], limit=4) == ["popup_store"]


@pytest.mark.unit
def test_카테고리가_다섯_종_이상이면_최대_네_종만_남고_빈_슬러그는_제외된다():
    from web.views.events import _dedupe_category_slugs

    slugs = ["", "exhibition", "popup_store", "exhibition", "concert", "fan_meeting", "theater_bonus"]

    assert _dedupe_category_slugs(slugs, limit=4) == [
        "exhibition", "popup_store", "concert", "fan_meeting",
    ]


@pytest.mark.django_db
def test_초안_행사는_홈_달력에_나타나지_않는다(make_draft_event):
    today = date(2026, 9, 16)
    make_draft_event(
        title="초안 행사",
        category="popup_store",
        start_date=date(2026, 9, 16),
        end_date=date(2026, 9, 16),
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
    cell = cells[date(2026, 9, 16)]
    assert cell["count"] == 0
    assert cell["categories"] == []
    assert calendar["selected_rows"] == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("event_count", "expected_rows"),
    [(6, 5), (0, 0)],
    ids=["여섯_건_상한", "행사_없음"],
)
def test_선택한_날짜의_행사는_최대_다섯_건까지_담기고_전체_건수는_따로_담긴다(
    make_event, event_count, expected_rows
):
    today = date(2026, 9, 16)
    for i in range(event_count):
        make_event(
            title=f"오늘 행사 {i}",
            start_date=date(2026, 9, 10),
            end_date=date(2026, 9, 20),
        )
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/")

    calendar = resp.context["home_calendar"]
    assert len(calendar["selected_rows"]) == expected_rows
    assert calendar["selected_count"] == event_count


@pytest.mark.django_db
def test_선택일_행은_행사의_파생_표시값을_담는다(make_event):
    today = date(2026, 9, 16)
    make_event(
        title="팝업",
        category="popup_store",
        start_date=date(2026, 9, 10),
        end_date=date(2026, 9, 20),
    )
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/")

    calendar = resp.context["home_calendar"]
    row = calendar["selected_rows"][0]
    assert row["event"].title == "팝업"
    assert row["category_slug"] == "popup_store"
    assert row["category_label"] == "팝업스토어"
    assert row["status_slug"] == "closing_soon"
    assert row["status_label"] == "종료 임박"
    assert row["dday"] == 4


@pytest.mark.django_db
def test_범례는_표시_달에_실제로_있는_카테고리만_어휘_순서로_담는다(make_event):
    today = date(2026, 9, 16)
    make_event(
        title="전시",
        category="exhibition",
        start_date=date(2026, 9, 3),
        end_date=date(2026, 9, 5),
    )
    make_event(
        title="팝업",
        category="popup_store",
        start_date=date(2026, 9, 20),
        end_date=date(2026, 9, 22),
    )
    make_event(
        title="미분류",
        category="",
        start_date=date(2026, 9, 8),
        end_date=date(2026, 9, 8),
    )
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/")

    calendar = resp.context["home_calendar"]
    assert calendar["legend"] == [
        {"slug": "popup_store", "label": "팝업스토어"},
        {"slug": "exhibition", "label": "전시"},
    ]


@pytest.mark.django_db
def test_홈_응답의_달력_전체_보기_링크는_표시_달로_이동한다():
    today = date(2026, 9, 16)
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/", {"month": "2026-11"})

    assert (
        _find_href(resp.content.decode(), "달력 전체 보기 ›")
        == "/events/calendar/?month=2026-11"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("event_count", "expected_href"),
    [
        (1, "/events/calendar/?month=2026-09&date=2026-09-20#selected-date"),
        (0, None),
    ],
    ids=["행사_있음", "행사_없음"],
)
def test_홈_응답의_모두_보기_링크는_선택한_날짜를_담는다(make_event, event_count, expected_href):
    today = date(2026, 9, 16)
    for _ in range(event_count):
        make_event(
            title="20일 행사",
            start_date=date(2026, 9, 20),
            end_date=date(2026, 9, 20),
        )
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/", {"date": "2026-09-20"})

    body = resp.content.decode()
    assert (
        _find_href(body, f"이 날짜의 이벤트 {event_count}개 모두 보기 ›")
        == expected_href
    )


@pytest.mark.django_db
def test_이번_달_밖_채움_칸에는_행사_건수와_카테고리를_담지_않는다(make_event):
    today = date(2026, 9, 16)
    make_event(
        title="월말 걸친 팝업",
        category="popup_store",
        start_date=date(2026, 8, 28),
        end_date=date(2026, 9, 3),
    )
    with patch("web.views.events.timezone.localdate", return_value=today):
        resp = Client().get("/")

    calendar = resp.context["home_calendar"]
    cells = {day["date"]: day for week in calendar["weeks"] for day in week}
    assert cells[date(2026, 8, 31)]["in_month"] is False
    assert cells[date(2026, 8, 31)]["count"] == 0
    assert cells[date(2026, 8, 31)]["categories"] == []
    assert cells[date(2026, 9, 1)]["count"] == 1


@pytest.mark.django_db
def test_카테고리가_없는_행사는_건수와_아젠다에는_남고_점과_범례에서는_빠진다(make_event):
    today = date(2026, 9, 16)
    make_event(
        title="미분류 행사",
        category="",
        start_date=date(2026, 9, 16),
        end_date=date(2026, 9, 16),
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
    cell = cells[date(2026, 9, 16)]
    assert cell["count"] == 1
    assert cell["categories"] == []
    assert calendar["selected_count"] == 1
    assert [row["event"].title for row in calendar["selected_rows"]] == ["미분류 행사"]
    assert calendar["legend"] == []
