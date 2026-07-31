"""스태프 콘솔 대시보드용 읽기 전용 계층.

조회 로직은 뷰가 아니라 여기 둔다(drafts/queries.py, events/queries.py와 같은 구조).
"""
from datetime import datetime, time, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import StaffActionLog


def recent_staff_actions(limit=10):
    """최근 StaffActionLog를 최신순으로 limit개 반환한다.

    select_related로 N+1 쿼리를 막는다. 모델 전체를 반환하지만 대시보드
    템플릿은 ip_address/user_agent를 렌더링하지 않는다 — 그 값은 슈퍼유저
    전용(staff/admin.py)으로 남겨야 한다.
    """
    return list(
        StaffActionLog.objects.select_related(
            "actor", "target_draft", "target_event"
        ).all()[:limit]
    )


def staff_actions_count_since(days=7, offset=0):
    """지난 구간의 StaffActionLog 건수를 센다.

    구간은 [now-(offset+days), now-offset) 반열림 구간이라 경계에 걸친
    행이 두 번 세이지 않는다. offset을 늘리면 더 과거 구간과 비교할 수
    있다(예: 이번 주 대 지난 주).
    """
    window_end = timezone.now() - timedelta(days=offset)
    window_start = window_end - timedelta(days=days)
    return StaffActionLog.objects.filter(
        created_at__gte=window_start, created_at__lt=window_end
    ).count()


def staff_actions_per_day(days=14):
    """최근 `days`일간 하루 단위 StaffActionLog 건수를 반환한다.

    UTC가 아니라 한국 시간 기준 날짜로 묶는다 — UTC로 묶으면 자정 근처
    로그가 다른 날짜로 잘못 집계된다. 로그가 0건인 날도 count=0으로 채워
    반환해 호출부가 직접 빈 날짜를 메울 필요가 없다.
    """
    current_tz = timezone.get_current_timezone()
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    window_start = timezone.make_aware(
        datetime.combine(start_date, time.min), current_tz
    )

    counts_by_date = {
        row["day"]: row["count"]
        for row in (
            StaffActionLog.objects.filter(created_at__gte=window_start)
            .annotate(day=TruncDate("created_at", tzinfo=current_tz))
            .values("day")
            .annotate(count=Count("id"))
            .values("day", "count")
        )
    }

    return [
        {
            "date": start_date + timedelta(days=offset),
            "count": counts_by_date.get(start_date + timedelta(days=offset), 0),
        }
        for offset in range(days)
    ]
