"""순수 달력 그리드 표현 도우미.

의도적으로 `events`/`archive`(또는 다른 Django 앱) 임포트가 없다 — `core`
표현 코드는 두 도메인의 조회 결과를 조립할 뿐, 그 비즈니스 상태를
소유하거나 재계산해서는 안 된다. 이 경계는
tests/core/test_calendar_grid.py의 AST 가드가 강제하므로 이 모듈은
표준 라이브러리만 사용한다.
"""
import calendar
from dataclasses import dataclass
# `from datetime import date`가 아니라 별칭을 쓴다: 아래 데이터클래스
# 필드 이름도 `date`라서, `field: T = default` 형태는 클래스 본문에서
# 어노테이션 `T`를 평가하기 *전에* 기본값을 필드 이름에 먼저 바인딩한다.
# 별칭 없이 같은 이름으로 임포트하면 이 필드의 어노테이션이 타입을
# 참조하려는 시점엔 이미 date 인스턴스로 재바인딩된 뒤일 것이다.
from datetime import date as _date
from datetime import timedelta


@dataclass(frozen=True)
class CalendarDayCell:
    """월 그리드의 날짜 셀 하나.

    7칸짜리 한 주를 채우기 위해 앞뒤 인접 달에서 가져온 날짜는
    `in_month`가 False다("현재 월 밖의 날짜는 약하게 표시한다"). 채움
    셀의 달력 날짜가 datetime이 표현 가능한 범위(1~9999년)를 벗어나는
    드문 경우엔 `date`가 `None`이며, 이때는 항상 `in_month=False`와
    짝을 이룬다.
    """

    date: _date | None
    in_month: bool


def month_grid(year, month):
    """주어진 달을 일요일부터 시작하는 정확히 7칸짜리 CalendarDayCell
    리스트들(주 단위 리스트의 리스트)로 반환한다.

    `calendar.Calendar.monthdatescalendar`를 쓰지 않고 날짜 수 계산으로
    직접 만든다: 그 표준 라이브러리 헬퍼는 채움 날짜를 항상 실제 `date`로
    만들어내는데, 채움 날짜가 "0년"(예: year=1, month=1)이나 "10000년"
    (예: year=9999, month=12)에 걸치면 datetime의 MINYEAR..MAXYEAR
    범위를 벗어나 `ValueError`가 난다. 여기서는 각 채움 후보 날짜를
    `timedelta` 연산으로만 계산하고, 범위 안일 때만 실제 `date`로
    남긴다. 범위를 벗어나면 예외를 전파하는 대신 `date=None,
    in_month=False`로 낮춘다.
    """
    first_of_month = _date(year, month, 1)
    days_in_month = calendar.monthrange(year, month)[1]
    # 1일의 일요일 기준 열 인덱스: Python weekday()는 월=0..일=6이므로
    # 일=0, 토=6이 되도록 이동시킨다.
    leading_fillers = (first_of_month.weekday() + 1) % 7
    total_cells = leading_fillers + days_in_month
    total_weeks = -(-total_cells // 7)  # 올림 나눗셈. 실수 반올림 없이 계산.

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
    """조회한 (year, month)의 기본 선택 날짜를 반환한다: 조회한 달이 이번
    달이면 오늘, 아니면 1일."""
    if (year, month) == (today.year, today.month):
        return today
    return _date(year, month, 1)
