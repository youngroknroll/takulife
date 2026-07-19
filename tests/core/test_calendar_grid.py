"""Calendar grid pure functions (dual-calendar Test List §단계 4: CAL-4-01~07).

core.calendar_grid does not exist yet:
- CAL-4-01~05 import month_grid/default_selected_date directly, so the whole
  file is expected to fail at collection with ImportError until the module
  is added (mirrors tests/archive/test_activity_log_entry.py's convention).
- CAL-4-06 additionally reads core/calendar_grid.py's source text directly
  (AST import-boundary guard, mirroring tests/core/test_architecture_boundaries.py's
  _imported_modules technique) — before the module exists this specific
  assertion would instead fail at read time with FileNotFoundError, which is
  also an expected Red for a not-yet-created file, not a false-positive pass.
- CAL-4-07 (added after CAL-5 web-layer work surfaced a real gap in the
  already-merged month_grid): the current implementation raises
  ``ValueError`` for year=1/month=1 and year=9999/month=12, because the
  leading/trailing filler week needs a real ``date()`` one day into
  "year 0" or "year 10000" — outside datetime's representable range
  (MINYEAR=1/MAXYEAR=9999). This test is expected to fail with that
  uncaught ValueError, not an assertion mismatch, until month_grid is fixed
  at the source (next message).

Assumed shape (unit-tested, no DB):
- ``month_grid(year, month)`` returns a list of weeks; each week is a list
  of exactly 7 day cells, Sunday first. Each cell exposes ``.in_month``
  (bool, True iff the cell falls within the queried (year, month)) and
  ``.date``: a real ``date`` for every in-month cell and every filler cell
  that datetime can represent, but ``None`` (cell contract extended by
  CAL-4-07) for a filler cell whose calendar date would fall outside
  year 1..9999 — always paired with ``in_month is False``.
- ``default_selected_date(year, month, today)`` returns a plain ``date``:
  ``today`` itself when (year, month) is today's month, otherwise the 1st.
"""
import ast
import calendar
from datetime import date
from pathlib import Path

import pytest

from core.calendar_grid import default_selected_date, month_grid

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# CAL-4-01 — Sunday-first, 7-column weekly grid
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_월_격자를_생성하면_일요일부터_토요일까지_7열로_구성된다():
    weeks = month_grid(2026, 7)

    assert weeks
    for week in weeks:
        assert len(week) == 7
        assert week[0].date.weekday() == 6  # Sunday (Python: Monday=0..Sunday=6)
        assert week[6].date.weekday() == 5  # Saturday


# ---------------------------------------------------------------------------
# CAL-4-02 — leading days from the previous month are marked out-of-month
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_이전_달_날짜가_포함되면_다른_월로_표시된다():
    # 2026-07-01 is a Wednesday, so the first week carries 2026-06-28~30
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
# CAL-4-03 — trailing days from the next month are marked out-of-month
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_다음_달_날짜가_포함되면_다른_월로_표시된다():
    # 2026-07-31 is a Friday, so the last week carries 2026-08-01.
    weeks = month_grid(2026, 7)
    last_week = weeks[-1]

    trailing_other_month = [cell for cell in last_week if cell.date > date(2026, 7, 31)]

    assert trailing_other_month
    assert all(cell.in_month is False for cell in trailing_other_month)
    assert all(
        cell.in_month is True for cell in last_week if cell.date <= date(2026, 7, 31)
    )


# ---------------------------------------------------------------------------
# CAL-4-04 — current month defaults the selected date to today
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_조회_월이_이번_달이면_기본_선택_날짜는_오늘이다():
    selected = default_selected_date(year=2026, month=7, today=date(2026, 7, 19))

    assert selected == date(2026, 7, 19)


# ---------------------------------------------------------------------------
# CAL-4-05 — any other month defaults the selected date to the 1st
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_조회_월이_다른_달이면_기본_선택_날짜는_1일이다():
    selected = default_selected_date(year=2026, month=8, today=date(2026, 7, 19))

    assert selected == date(2026, 8, 1)


# ---------------------------------------------------------------------------
# CAL-4-06 — the grid module stays free of events/archive imports
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
# CAL-4-07 — datetime-range boundary months (year 1 / year 9999) build a
# grid without raising, representing any out-of-range filler cell as
# date=None/in_month=False instead of crashing
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
