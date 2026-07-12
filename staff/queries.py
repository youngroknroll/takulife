"""Public read layer for the staff console dashboard.

Provides reusable read logic for staff-facing summaries. Business logic
lives here, not in the view layer (mirrors drafts/queries.py, events/queries.py).
"""
from datetime import datetime, time, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import StaffActionLog


def recent_staff_actions(limit=10):
    """Return the most recent StaffActionLog rows, newest first, limited.

    select_related("actor", "target_draft", "target_event") avoids N+1
    queries when the dashboard template reads actor email / draft title /
    event title for each row.

    Returns full StaffActionLog objects (not a dict projection): this is a
    staff-internal read, so exposing the full model here is safe. The
    dashboard template itself only renders actor/action/target_draft/
    target_event/created_at and must not render ip_address/user_agent
    (those stay superuser-only, surfaced only via staff/admin.py).
    """
    return list(
        StaffActionLog.objects.select_related(
            "actor", "target_draft", "target_event"
        ).all()[:limit]
    )


def staff_actions_count_since(days=7, offset=0):
    """Return the count of StaffActionLog rows created in a trailing window.

    The window is the half-open interval [now-(offset+days), now-offset),
    so consecutive windows never double-count a row that lands exactly on
    a boundary. offset shifts the window into the past: offset=0 is "the
    last N days", offset=N is "the N days before that" — used to compare
    the current period against the prior one (e.g. this week vs last week).
    """
    window_end = timezone.now() - timedelta(days=offset)
    window_start = window_end - timedelta(days=days)
    return StaffActionLog.objects.filter(
        created_at__gte=window_start, created_at__lt=window_end
    ).count()


def staff_actions_per_day(days=14):
    """Return per-day StaffActionLog counts for the trailing `days` days.

    Buckets by local calendar day (Asia/Seoul), not UTC date: a log created
    at 15:30 UTC lands at 00:30 the next day in KST, so bucketing on the raw
    UTC date would attribute it to the wrong day. Days with zero logs are
    included with count=0 so callers can render a fixed-width chart without
    gap-filling themselves. Result is ordered ascending, ending today.
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
