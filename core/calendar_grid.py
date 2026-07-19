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

# 6 = Sunday, per Python's calendar module weekday numbering (Monday=0).
_SUNDAY_FIRST = calendar.Calendar(firstweekday=6)


@dataclass(frozen=True)
class CalendarDayCell:
    """One day cell in a month grid.

    `in_month` is False for the leading/trailing days of the adjacent months
    used to fill out a full 7-column week (service design §9.1: "현재 월 밖의
    날짜는 약하게 표시한다").
    """

    date: _date
    in_month: bool


def month_grid(year, month):
    """Return the given month as a list of weeks, each a list of exactly 7
    CalendarDayCell entries, Sunday first (service design §9.1)."""
    return [
        [CalendarDayCell(date=day, in_month=day.month == month) for day in week]
        for week in _SUNDAY_FIRST.monthdatescalendar(year, month)
    ]


def default_selected_date(year, month, *, today):
    """Return the default selected date for a queried (year, month): today
    itself when the queried month is the current month, otherwise the 1st
    (service design §9.1)."""
    if (year, month) == (today.year, today.month):
        return today
    return _date(year, month, 1)
