"""Tests for the home page view context (core.views.home).

Covers:
- "카테고리로 둘러보기" tiles: one tile per vocab category, in vocab order,
  each carrying the count of *published* events in that category.
- Context key caps (ongoing/closing/recent limited to 15).
- D-5 closing window (home-only selection concern).
- Guard: D+5 events in closing_rows still have status_slug == "ongoing".
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
        assert len(resp.context["ongoing_rows"]) == 15

    def test_recent_capped_at_15(self, make_event):
        today = date(2026, 6, 26)
        self._make_recent(make_event, 16)
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["recent_rows"]) == 15

    def test_closing_capped_at_15(self, make_event):
        today = date(2026, 6, 26)
        self._make_closing(make_event, today, 16)
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["closing_rows"]) == 15

    def test_all_empty_keys_present_as_empty_lists(self):
        resp = Client().get("/")
        assert resp.context["ongoing_rows"] == []
        assert resp.context["closing_rows"] == []
        assert resp.context["recent_rows"] == []
        assert resp.context["category_tiles"] is not None
        assert resp.context["popular_rows"] == []


@pytest.mark.django_db
class TestHomeClosingWindow:
    """Home view uses a D-5 closing window (not the global D-4 window)."""

    def test_event_ending_today_plus_5_appears_in_closing_rows(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+5 closing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_ids = [row["event"].id for row in resp.context["closing_rows"]]
        assert event.id in closing_ids

    def test_event_ending_today_plus_6_does_not_appear_in_closing_rows(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+6 not closing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=6),
        )
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_ids = [row["event"].id for row in resp.context["closing_rows"]]
        assert event.id not in closing_ids


@pytest.mark.django_db
class TestHomeSlidersDropEndedEvents:
    """Sliders hide events whose period has passed (end_date < today)."""

    def test_ended_event_excluded_from_recent_rows(self, make_event):
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
        recent_ids = [row["event"].id for row in resp.context["recent_rows"]]
        assert ended.id not in recent_ids
        assert live.id in recent_ids

    def test_event_without_end_date_kept_in_recent_rows(self, make_event):
        today = date(2026, 6, 26)
        no_dates = make_event(title="No dates")
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        recent_ids = [row["event"].id for row in resp.context["recent_rows"]]
        assert no_dates.id in recent_ids


@pytest.mark.django_db
class TestHomePosterSectionsAlwaysRenderSlider:
    """The 3 poster sections (이번 주/곧 종료/새 이벤트) used to branch on row
    count — a section at or below its threshold (ongoing<=6, closing<=3,
    recent<=6) rendered a static .poster-card-grid instead of the
    hscroll-wrap slider the other sections used, producing a visibly
    different layout (no arrows, left-aligned static grid) whenever a
    section happened to have few rows. All 3 sections now always render the
    hscroll-wrap markup regardless of row count; hscroll.js hides the arrows
    via visibility when there's nothing to scroll."""

    def test_closing_section_renders_hscroll_wrap_with_few_rows(self, make_event):
        today = date(2026, 6, 26)
        for i in range(3):
            make_event(
                title=f"Closing {i}",
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=i % 5 + 1),
            )
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")

        assert len(resp.context["closing_rows"]) == 3
        body = resp.content.decode()
        assert 'id="hscroll-closing"' in body
        assert "poster-card-grid" not in body


@pytest.mark.django_db
class TestHomeClosingStatusDivergence:
    """Guard: a D+5 event selected into closing_rows is still status_slug=="ongoing".

    This documents the intentional divergence between:
    - Home selection: ending_within_days(5) — selects D+5 events.
    - Status classification: derive_event_display uses CLOSING_SOON_DAYS==4, so
      a D+5 event is still "ongoing" from a status perspective.

    If CLOSING_SOON_DAYS is ever changed to 5, this test will catch the
    accidental coupling.
    """

    def test_d5_event_in_closing_rows_has_status_slug_ongoing(self, make_event):
        today = date(2026, 6, 26)
        make_event(
            title="D+5 boundary",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        with patch("core.views.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_rows = resp.context["closing_rows"]
        d5_rows = [r for r in closing_rows if r["event"].title == "D+5 boundary"]
        assert len(d5_rows) == 1
        assert d5_rows[0]["status_slug"] == "ongoing"


@pytest.mark.django_db
class TestHomeCollectionSnapshotContext:
    """Collection-first home (H-1 행위 C): a logged-in user's personalized
    snapshot — collection_summary/recent_goods/unrecorded/upcoming_planned/
    snapshot_active. archive.models is imported inside each test function
    (not at module top) since only this class needs it and tests/events/
    carries no archive factory fixtures (make_status/make_collection_item
    live in tests/archive/conftest.py, out of scope here)."""

    SNAPSHOT_KEYS = (
        "collection_summary",
        "recent_goods",
        "unrecorded",
        "upcoming_planned",
        "snapshot_active",
    )

    def test_anonymous_response_has_no_snapshot_context_keys(self):
        resp = Client().get("/")

        assert resp.status_code == 200
        for key in self.SNAPSHOT_KEYS:
            assert key not in resp.context

    def test_anonymous_response_has_no_snapshot_markup(self):
        """§7-b-1: the template gates the whole panel behind {% if
        request.user.is_authenticated %} as a second, template-level
        defence beyond the context-key check above — an anonymous response
        must carry zero bytes of the panel's markup, not just miss its
        context keys."""
        resp = Client().get("/")

        assert b"snapshot-panel" not in resp.content
        assert b"hscroll-snap" not in resp.content

    def test_authenticated_response_has_snapshot_context_keys_owner_scoped(
        self, make_user, make_event
    ):
        from archive.models import CollectionItem, UserEventStatus

        user = make_user()
        other = make_user()
        today = date(2026, 6, 26)
        future = today + timedelta(days=5)

        CollectionItem.objects.create(user=user, name="보유 아이템")
        visited_event = make_event(title="다녀온 행사")
        UserEventStatus.objects.create(
            user=user, event=visited_event, status=UserEventStatus.Status.VISITED
        )
        upcoming_event = make_event(title="다가오는 행사", start_date=future)
        UserEventStatus.objects.create(
            user=user, event=upcoming_event, status=UserEventStatus.Status.PLANNED
        )

        # other user seeded identically on all 3 axes — must never leak into
        # this user's snapshot.
        CollectionItem.objects.create(user=other, name="타 유저 보유 아이템")
        other_visited_event = make_event(title="타 유저 다녀온 행사")
        UserEventStatus.objects.create(
            user=other, event=other_visited_event, status=UserEventStatus.Status.VISITED
        )
        other_upcoming_event = make_event(title="타 유저 다가오는 행사", start_date=future)
        UserEventStatus.objects.create(
            user=other, event=other_upcoming_event, status=UserEventStatus.Status.PLANNED
        )

        client = Client()
        client.force_login(user)
        with patch("core.views.timezone.localdate", return_value=today):
            resp = client.get("/")

        assert resp.context["collection_summary"] == {"owned_count": 1, "wanted_count": 0}
        assert resp.context["recent_goods"][0].name == "보유 아이템"
        assert resp.context["unrecorded"][0]["subject"]["subject_type"] == "event"
        assert resp.context["unrecorded"][0]["subject"]["subject_id"] == visited_event.id
        assert resp.context["upcoming_planned"][0]["event"].id == upcoming_event.id
        assert "status_slug" in resp.context["upcoming_planned"][0]

    def test_recent_goods_capped_at_5(self, make_user):
        from archive.models import CollectionItem

        user = make_user()
        for i in range(6):
            CollectionItem.objects.create(user=user, name=f"아이템{i}")

        client = Client()
        client.force_login(user)
        resp = client.get("/")

        assert len(resp.context["recent_goods"]) == 5

    def test_unrecorded_capped_at_5(self, make_user, make_event):
        from archive.models import UserEventStatus

        user = make_user()
        for i in range(6):
            event = make_event(title=f"미완성 기록 행사{i}")
            UserEventStatus.objects.create(
                user=user, event=event, status=UserEventStatus.Status.VISITED
            )

        client = Client()
        client.force_login(user)
        resp = client.get("/")

        assert len(resp.context["unrecorded"]) == 5

    def test_upcoming_planned_capped_at_4(self, make_user, make_event):
        from archive.models import UserEventStatus

        user = make_user()
        today = date(2026, 6, 26)
        for i in range(5):
            event = make_event(
                title=f"다가오는 행사{i}", start_date=today + timedelta(days=i + 1)
            )
            UserEventStatus.objects.create(
                user=user, event=event, status=UserEventStatus.Status.PLANNED
            )

        client = Client()
        client.force_login(user)
        with patch("core.views.timezone.localdate", return_value=today):
            resp = client.get("/")

        assert len(resp.context["upcoming_planned"]) == 4

    def test_snapshot_active_true_when_any_axis_has_data(self, make_user):
        """snapshot_active is owned+wanted (H4) — deliberately different from
        mypage's collection_count, which counts owned only. A wanted-only
        collection (owned 0) must still activate the snapshot."""
        from archive.models import CollectionItem

        user = make_user()
        CollectionItem.objects.create(user=user, name="구하는 아이템", is_wanted=True)

        client = Client()
        client.force_login(user)
        resp = client.get("/")

        assert resp.context["snapshot_active"] is True

    def test_snapshot_active_false_when_all_axes_empty(self, make_user):
        user = make_user()

        client = Client()
        client.force_login(user)
        resp = client.get("/")

        assert resp.context["snapshot_active"] is False

    def test_get_home_does_not_mutate_user_event_status_count_or_updated_at(
        self, make_user, make_event
    ):
        from archive.models import UserEventStatus

        user = make_user()
        today = date(2026, 6, 26)
        event = make_event(title="예정 행사", start_date=today + timedelta(days=5))
        status = UserEventStatus.objects.create(
            user=user, event=event, status=UserEventStatus.Status.PLANNED
        )
        original_updated_at = status.updated_at

        client = Client()
        client.force_login(user)
        with patch("core.views.timezone.localdate", return_value=today):
            client.get("/")
            client.get("/")

        status.refresh_from_db()
        assert UserEventStatus.objects.count() == 1
        assert status.updated_at == original_updated_at
