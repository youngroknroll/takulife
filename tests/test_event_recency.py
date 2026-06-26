"""Unit tests for events.presenters.is_recently_added (NEW badge window).

An event is "NEW" while fewer than NEW_WINDOW_DAYS (10) days have passed since
its created_at. Day 0..9 = NEW; day 10 = no longer new. No DB needed — the helper
only reads event.created_at, so plain stub objects exercise the boundaries.
"""
from datetime import date, datetime
from types import SimpleNamespace

from events.presenters import NEW_WINDOW_DAYS, is_recently_added

TODAY = date(2026, 6, 27)


def _event(created):
    return SimpleNamespace(created_at=created)


class TestIsRecentlyAdded:
    def test_window_is_ten_days(self):
        assert NEW_WINDOW_DAYS == 10

    def test_created_today_is_new(self):
        assert is_recently_added(_event(datetime(2026, 6, 27, 9, 0)), today=TODAY) is True

    def test_created_nine_days_ago_is_new(self):
        # boundary: day 9 still NEW
        assert is_recently_added(_event(datetime(2026, 6, 18, 23, 0)), today=TODAY) is True

    def test_created_exactly_ten_days_ago_is_not_new(self):
        # boundary: day 10 no longer NEW
        assert is_recently_added(_event(datetime(2026, 6, 17, 1, 0)), today=TODAY) is False

    def test_created_long_ago_is_not_new(self):
        assert is_recently_added(_event(datetime(2020, 1, 1, 0, 0)), today=TODAY) is False

    def test_missing_created_at_is_not_new(self):
        assert is_recently_added(_event(None), today=TODAY) is False
