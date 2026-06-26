"""Tests for the home page view context (core.views.home).

Covers:
- "카테고리로 둘러보기" tiles: one tile per vocab category, in vocab order,
  each carrying the count of *published* events in that category.
- Context key caps (ongoing/closing/recent limited to 15).
- D-5 closing window (home-only selection concern).
- Guard: D+5 events in closing_events still have status_slug == "ongoing".
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch

from django.test import Client

from events.models import Event


@pytest.mark.django_db
class TestHomeCategoryTiles:
    def test_tiles_cover_every_category_in_vocab_order(self):
        resp = Client().get("/")

        assert resp.status_code == 200
        slugs = [t["slug"] for t in resp.context["category_tiles"]]
        assert slugs == [
            "popup_store",
            "collaboration_cafe",
            "theater_bonus",
            "goods_reservation",
            "exhibition",
            "fan_meeting",
        ]

    def test_tile_counts_only_published_events_per_category(self, make_event):
        make_event(category="popup_store")
        make_event(category="popup_store")
        make_event(category="exhibition")
        # a draft in popup_store must NOT be counted
        make_event(category="popup_store", publish_status=Event.PublishStatus.DRAFT)

        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["popup_store"]["count"] == 2
        assert tiles["exhibition"]["count"] == 1
        assert tiles["collaboration_cafe"]["count"] == 0

    def test_tiles_carry_korean_labels(self):
        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["popup_store"]["label"] == "팝업스토어"
        assert tiles["theater_bonus"]["label"] == "극장 특전"
        assert tiles["fan_meeting"]["label"] == "팬미팅"


@pytest.mark.django_db
class TestHomeContextCaps:
    """Home view limits each section to 15 items even when more exist."""

    def _make_ongoing(self, make_event, today, n):
        for i in range(n):
            make_event(
                title=f"Ongoing {i}",
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=30),
            )

    def _make_recent(self, make_event, n):
        for i in range(n):
            make_event(title=f"Recent {i}")

    def _make_closing(self, make_event, today, n):
        for i in range(n):
            make_event(
                title=f"Closing {i}",
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=i % 5 + 1),  # D+1 to D+5
            )

    def test_ongoing_capped_at_15(self, make_event):
        today = date(2026, 6, 26)
        self._make_ongoing(make_event, today, 16)
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["ongoing_events"]) == 15

    def test_recent_capped_at_15(self, make_event):
        today = date(2026, 6, 26)
        self._make_recent(make_event, 16)
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["recent_events"]) == 15

    def test_closing_capped_at_15(self, make_event):
        today = date(2026, 6, 26)
        self._make_closing(make_event, today, 16)
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["closing_events"]) == 15

    def test_all_empty_keys_present_as_empty_lists(self):
        resp = Client().get("/")
        assert resp.context["ongoing_events"] == []
        assert resp.context["closing_events"] == []
        assert resp.context["recent_events"] == []
        assert resp.context["category_tiles"] is not None
        assert resp.context["popular_events"] == []


@pytest.mark.django_db
class TestHomeClosingWindow:
    """Home view uses a D-5 closing window (not the global D-4 window)."""

    def test_event_ending_today_plus_5_appears_in_closing_events(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+5 closing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_ids = [row["event"].id for row in resp.context["closing_events"]]
        assert event.id in closing_ids

    def test_event_ending_today_plus_6_does_not_appear_in_closing_events(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+6 not closing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=6),
        )
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_ids = [row["event"].id for row in resp.context["closing_events"]]
        assert event.id not in closing_ids


@pytest.mark.django_db
class TestHomeSlidersDropEndedEvents:
    """Sliders hide events whose period has passed (end_date < today)."""

    def test_ended_event_excluded_from_recent_events(self, make_event):
        today = date(2026, 6, 26)
        ended = make_event(
            title="Ended",
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=1),
        )
        live = make_event(
            title="Still running",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=3),
        )
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        recent_ids = [row["event"].id for row in resp.context["recent_events"]]
        assert ended.id not in recent_ids
        assert live.id in recent_ids

    def test_event_without_end_date_kept_in_recent_events(self, make_event):
        today = date(2026, 6, 26)
        no_dates = make_event(title="No dates")
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        recent_ids = [row["event"].id for row in resp.context["recent_events"]]
        assert no_dates.id in recent_ids


@pytest.mark.django_db
class TestHomeClosingStatusDivergence:
    """Guard: a D+5 event selected into closing_events is still status_slug=="ongoing".

    This documents the intentional divergence between:
    - Home selection: ending_within_days(5) — selects D+5 events.
    - Status classification: derive_event_display uses CLOSING_SOON_DAYS==4, so
      a D+5 event is still "ongoing" from a status perspective.

    If CLOSING_SOON_DAYS is ever changed to 5, this test will catch the
    accidental coupling.
    """

    def test_d5_event_in_closing_events_has_status_slug_ongoing(self, make_event):
        today = date(2026, 6, 26)
        make_event(
            title="D+5 boundary",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_events = resp.context["closing_events"]
        d5_rows = [r for r in closing_events if r["event"].title == "D+5 boundary"]
        assert len(d5_rows) == 1
        assert d5_rows[0]["status_slug"] == "ongoing"
