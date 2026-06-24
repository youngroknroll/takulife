"""Per-event display derivation for the events domain.

derive_event_display() computes status and D-day purely from an Event's
date fields, using the same thresholds as EventQuerySet.with_public_status().

Status classification (matches querysets.py exactly):
  upcoming     : start_date > today
  closing_soon : start_date <= today AND end_date >= today AND end_date <= today + CLOSING_SOON_DAYS
  ongoing      : start_date <= today AND end_date >= today (and NOT closing_soon)
  ended        : end_date < today

D-day convention:
  upcoming  -> days until start_date  (positive integer)
  ongoing / closing_soon -> days until end_date  (non-negative integer)
  ended     -> None

NULL safety: if either start_date or end_date is None, returns status=None, dday=None.

This module MUST NOT import from `core` (one-way dependency: core -> events).
"""
from datetime import timedelta

from django.utils import timezone

from .querysets import CLOSING_SOON_DAYS


def derive_event_display(event, *, today=None):
    """Return a dict with 'status' and 'dday' for a single Event instance.

    Both values are None when either date is missing.
    Status slugs are the same canonical values used in the API status= filter.
    """
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

    # start_date <= today AND end_date >= today  (ongoing or closing_soon)
    dday = (end - today).days
    if end <= today + timedelta(days=CLOSING_SOON_DAYS):
        return {"status": "closing_soon", "dday": dday}

    return {"status": "ongoing", "dday": dday}
