"""이벤트 한 건의 상태·D-day를 날짜 필드만으로 계산한다.

상태 판정 기준은 EventQuerySet.with_public_status()와 반드시 동일하게 맞춘다.
이 모듈은 core를 임포트하면 안 된다(core -> events 단방향 의존 유지).
"""
from datetime import timedelta

from django.utils import timezone

from .querysets import CLOSING_SOON_DAYS

# 등록(created_at) 후 이 일수 미만이면 "새 등록"으로 표시한다. 0~9일차=NEW, 10일차부터 해제.
NEW_WINDOW_DAYS = 10


def is_recently_added(event, *, today=None, window_days=NEW_WINDOW_DAYS):
    """event가 최근 window_days일 안에 등록됐는지 여부. created_at이 없으면 False."""
    if today is None:
        today = timezone.localdate()
    created = getattr(event, "created_at", None)
    if created is None:
        return False
    return (today - created.date()).days < window_days


def derive_event_display(event, *, today=None):
    """이벤트 하나의 status·dday를 담은 dict를 반환한다. 날짜가 없으면 둘 다 None."""
    if today is None:
        today = timezone.localdate()

    start = event.start_date
    end = event.end_date

    if start is None or end is None:
        return {"status": None, "dday": None}

    if start > today:
        dday = (start - today).days
        return {"status": "upcoming", "dday": dday}

    if end < today:
        return {"status": "ended", "dday": None}

    dday = (end - today).days
    if end <= today + timedelta(days=CLOSING_SOON_DAYS):
        return {"status": "closing_soon", "dday": dday}

    return {"status": "ongoing", "dday": dday}
