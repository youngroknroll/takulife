"""Pure calendar-grid presentation helpers (dual-calendar plan §core layer).

Deliberately free of any `events`/`archive` (or other Django app) import —
`core` presentation code assembles the read results of those two domains but
must not own or recompute their business state (service design §5.1/§12).
This boundary is enforced by tests/core/test_calendar_grid.py's AST guard
(CAL-4-06), so this module stays stdlib-only.
"""
import calendar
from dataclasses import dataclass
# Aliased (not `from datetime import date`): the dataclass field below is
# also named `date`, and for `field: T = default` Python binds the default
# value to the field name *before* evaluating the annotation `T` at
# class-body scope — an unaliased same-named import would already be
# rebound (here, to a plain date instance) by the time this field's own
# annotation tried to reference the type.
from datetime import date as _date
from datetime import timedelta


@dataclass(frozen=True)
class CalendarDayCell:
    """One day cell in a month grid.

    `in_month` is False for the leading/trailing days of the adjacent months
    used to fill out a full 7-column week (service design §9.1: "현재 월 밖의
    날짜는 약하게 표시한다"). `date` is `None` (CAL-4-07) for the rare filler
    cell whose calendar date would fall outside datetime's representable
    range (year 1..9999) — always paired with `in_month=False`.
    """

    date: _date | None
    in_month: bool


def month_grid(year, month):
    """Return the given month as a list of weeks, each a list of exactly 7
    CalendarDayCell entries, Sunday first (service design §9.1).

    Built by hand (day-count arithmetic) rather than via
    `calendar.Calendar.monthdatescalendar`: that stdlib helper always
    materialises every filler day as a real `date`, which raises
    `ValueError` when a leading/trailing filler falls in "year 0" (e.g.
    year=1, month=1) or "year 10000" (e.g. year=9999, month=12) — outside
    datetime's MINYEAR..MAXYEAR range (CAL-4-07). Each candidate filler date
    is computed with plain `timedelta` arithmetic and only kept as a real
    `date` if that stays in range; otherwise the cell degrades to
    `date=None, in_month=False` instead of propagating the exception.
    """
    first_of_month = _date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    # Sunday-first column index of the 1st: Python's weekday() is
    # Monday=0..Sunday=6; shift so Sunday=0, Saturday=6.
    leading_fillers = (first_of_month.weekday() + 1) % 7
    total_cells = leading_fillers + days_in_month
    total_weeks = -(-total_cells // 7)  # ceil division, no float rounding

    cells = []
    for day_offset in range(-leading_fillers, total_weeks * 7 - leading_fillers):
        in_month = 0 <= day_offset < days_in_month
        try:
            cell_date = first_of_month + timedelta(days=day_offset)
        except OverflowError:
            cell_date = None
            in_month = False
        cells.append(CalendarDayCell(date=cell_date, in_month=in_month))

    return [cells[i : i + 7] for i in range(0, len(cells), 7)]


def default_selected_date(year, month, *, today):
    """Return the default selected date for a queried (year, month): today
    itself when the queried month is the current month, otherwise the 1st
    (service design §9.1)."""
    if (year, month) == (today.year, today.month):
        return today
    return _date(year, month, 1)
