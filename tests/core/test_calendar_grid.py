"""달력 격자 순수 함수(이중 달력 테스트 목록 §단계 4: CAL-4-01~07).

계약(단위 테스트, DB 불필요):
- ``month_grid(year, month)``는 주 목록을 돌려준다. 각 주는 정확히 7개의
  날짜 셀이며 일요일부터 시작한다. 각 셀은 ``.in_month``(질의한
  (year, month) 안이면 True)와 ``.date``를 갖는다 — 월 안의 셀과 datetime이
  표현 가능한 채움 셀은 실제 ``date``를, 1~9999년 범위 밖으로 나가는
  채움 셀은 ``None``을 갖는다(CAL-4-07에서 확장된 셀 계약이며 항상
  ``in_month is False``와 짝을 이룬다).
- ``default_selected_date(year, month, today)``는 평범한 ``date``를
  돌려준다: (year, month)가 오늘이 속한 달이면 ``today`` 자신을, 아니면
  1일을 돌려준다.

CAL-4-07: year=1/month=1, year=9999/month=12에서는 앞뒤 채움 주가 "0년"이나
"10000년" 쪽으로 하루 들어간 실제 ``date()``를 필요로 하는데, 이는
datetime이 표현 가능한 범위(MINYEAR=1/MAXYEAR=9999)를 벗어난다 — 그래서
그런 채움 셀만 date=None으로 표현한다.
"""
import ast
import calendar
from datetime import date
from pathlib import Path

import pytest

from core.calendar_grid import default_selected_date, month_grid

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# CAL-4-01 — 일요일부터 시작하는 7열 주간 격자
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_월_격자를_생성하면_일요일부터_토요일까지_7열로_구성된다():
    weeks = month_grid(2026, 7)

    assert weeks
    for week in weeks:
        assert len(week) == 7
        # 일요일(Python 기준 월=0..일=6)
        assert week[0].date.weekday() == 6
        # 토요일
        assert week[6].date.weekday() == 5


# ---------------------------------------------------------------------------
# CAL-4-02 — 이전 달의 앞쪽 날짜는 다른 월로 표시된다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_이전_달_날짜가_포함되면_다른_월로_표시된다():
    # 2026-07-01은 수요일이라 첫 주가 2026-06-28~30을 담는다
    # (python3 -c calendar.Calendar(firstweekday=6).monthdatescalendar 확인).
    weeks = month_grid(2026, 7)
    first_week = weeks[0]

    leading_other_month = [cell for cell in first_week if cell.date < date(2026, 7, 1)]

    assert leading_other_month
    assert all(cell.in_month is False for cell in leading_other_month)
    assert all(
        cell.in_month is True for cell in first_week if cell.date >= date(2026, 7, 1)
    )


# ---------------------------------------------------------------------------
# CAL-4-03 — 다음 달의 뒤쪽 날짜는 다른 월로 표시된다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_다음_달_날짜가_포함되면_다른_월로_표시된다():
    # 2026-07-31은 금요일이라 마지막 주가 2026-08-01을 담는다.
    weeks = month_grid(2026, 7)
    last_week = weeks[-1]

    trailing_other_month = [cell for cell in last_week if cell.date > date(2026, 7, 31)]

    assert trailing_other_month
    assert all(cell.in_month is False for cell in trailing_other_month)
    assert all(
        cell.in_month is True for cell in last_week if cell.date <= date(2026, 7, 31)
    )


# ---------------------------------------------------------------------------
# CAL-4-04 — 조회 월이 이번 달이면 기본 선택 날짜는 오늘이다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_조회_월이_이번_달이면_기본_선택_날짜는_오늘이다():
    selected = default_selected_date(year=2026, month=7, today=date(2026, 7, 19))

    assert selected == date(2026, 7, 19)


# ---------------------------------------------------------------------------
# CAL-4-05 — 조회 월이 다른 달이면 기본 선택 날짜는 1일이다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_조회_월이_다른_달이면_기본_선택_날짜는_1일이다():
    selected = default_selected_date(year=2026, month=8, today=date(2026, 7, 19))

    assert selected == date(2026, 8, 1)


# ---------------------------------------------------------------------------
# CAL-4-06 — 격자 모듈은 events/archive 임포트에서 자유롭다
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_달력_격자_모듈은_이벤트_아카이브_모듈을_임포트하지_않는다():
    tree = ast.parse((PROJECT_ROOT / "core/calendar_grid.py").read_text())
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)

    forbidden_names = {"events", "archive"}
    forbidden_prefixes = ("events.", "archive.")
    assert not {
        module
        for module in imported_modules
        if module in forbidden_names or module.startswith(forbidden_prefixes)
    }


# ---------------------------------------------------------------------------
# CAL-4-07 — datetime 표현 범위 경계 달(1년/9999년)도 예외 없이 격자를
# 만든다. 범위 밖 채움 셀은 크래시 대신 date=None/in_month=False로 표현한다
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "year, month",
    [(1, 1), (9999, 12)],
    ids=["최소_연도_1월", "최대_연도_12월"],
)
def test_달력_경계의_극단_월도_예외_없이_격자가_생성된다(year, month):
    weeks = month_grid(year, month)

    assert weeks
    for week in weeks:
        assert len(week) == 7
        for cell in week:
            if cell.date is None:
                assert cell.in_month is False
            else:
                assert isinstance(cell.date, date)

    # 당월의 모든 날짜는 반드시 어딘가의 셀에 실제 date로 존재해야 한다 —
    # 표현 불가한 필러 셀만 date=None이고, 당월 날짜 자체는 항상 표현 가능하다
    # (연·월 자체는 유효 범위 내이므로).
    all_dates = {cell.date for week in weeks for cell in week if cell.date is not None}
    days_in_month = calendar.monthrange(year, month)[1]
    for day in range(1, days_in_month + 1):
        assert date(year, month, day) in all_dates
