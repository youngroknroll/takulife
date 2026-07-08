"""Tests for events/queries.py and events/presenters.py: display derivation,
most-viewed/ending-soon querysets, and staff listing.

Covers:
- derive_event_display: status classification, closing_soon boundary, dday, null dates
- most_viewed / ending_within_days: EventQuerySet ordering/filtering methods
- list_staff_events: staff quality-warning drilldown listing (PR-E1)
"""
import pytest
from datetime import date, timedelta

from events.models import Event



# ---------------------------------------------------------------------------
# derive_event_display
# ---------------------------------------------------------------------------

class TestDeriveEventDisplay:
    def test_upcoming_status_and_dday(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today + timedelta(days=3), end_date=today + timedelta(days=10))
        result = derive_event_display(event, today=today)

        assert result["status"] == "upcoming"
        assert result["dday"] == 3  # days to start

    def test_ongoing_status_and_dday(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=2), end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert result["status"] == "ongoing"
        assert result["dday"] == 5  # days to end

    def test_closing_soon_at_exactly_4_days(self):
        """end_date == today + 4 days is exactly within the closing_soon window."""
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=1), end_date=today + timedelta(days=4))
        result = derive_event_display(event, today=today)

        assert result["status"] == "closing_soon"
        assert result["dday"] == 4

    def test_closing_soon_at_zero_days(self):
        """end_date == today is also closing_soon (ends today)."""
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=2), end_date=today)
        result = derive_event_display(event, today=today)

        assert result["status"] == "closing_soon"
        assert result["dday"] == 0

    def test_not_closing_soon_at_5_days(self):
        """end_date == today + 5 days is ongoing, NOT closing_soon."""
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=1), end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert result["status"] == "ongoing"
        assert result["dday"] == 5

    def test_ended_status_and_no_dday(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=10), end_date=today - timedelta(days=1))
        result = derive_event_display(event, today=today)

        assert result["status"] == "ended"
        assert result["dday"] is None

    def test_null_start_date_returns_none_status_and_dday(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=None, end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert result["status"] is None
        assert result["dday"] is None

    def test_null_end_date_returns_none_status_and_dday(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=1), end_date=None)
        result = derive_event_display(event, today=today)

        assert result["status"] is None
        assert result["dday"] is None

    def test_both_null_dates_returns_none_without_crash(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=None, end_date=None)
        result = derive_event_display(event, today=today)

        assert result["status"] is None
        assert result["dday"] is None

    def test_uses_today_default_when_not_provided(self):
        """When today is not provided, the function still returns a result dict."""
        from events.presenters import derive_event_display

        event = Event(start_date=None, end_date=None)
        result = derive_event_display(event)

        assert "status" in result
        assert "dday" in result

    def test_returns_dict_with_required_keys(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today + timedelta(days=1), end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert "status" in result
        assert "dday" in result


# ---------------------------------------------------------------------------
# most_viewed queryset method
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMostViewed:
    def test_returns_events_ordered_by_view_count_descending(self, make_event):
        low = make_event(title="Low")
        high = make_event(title="High")
        mid = make_event(title="Mid")

        Event.objects.filter(pk=low.pk).update(view_count=10)
        Event.objects.filter(pk=mid.pk).update(view_count=30)
        Event.objects.filter(pk=high.pk).update(view_count=50)

        result = list(Event.objects.published().most_viewed(5))
        ids = [e.id for e in result]
        assert ids.index(high.id) < ids.index(mid.id)
        assert ids.index(mid.id) < ids.index(low.id)

    def test_returns_at_most_limit_events(self, make_event):
        for i in range(7):
            make_event(title=f"Event {i}")

        result = list(Event.objects.published().most_viewed(5))
        assert len(result) <= 5

    def test_excludes_draft_events(self, make_event):
        published = make_event(title="Published")
        draft = make_event(title="Draft", publish_status=Event.PublishStatus.DRAFT)
        Event.objects.filter(pk=draft.pk).update(view_count=999)

        result = list(Event.objects.published().most_viewed(5))
        ids = [e.id for e in result]
        assert draft.id not in ids
        assert published.id in ids

    def test_equal_view_count_tiebreaks_by_id_descending(self, make_event):
        first = make_event(title="First")
        second = make_event(title="Second")

        # Both have same view_count (0 by default)
        result = list(Event.objects.published().most_viewed(5))
        ids = [e.id for e in result]
        # Higher id comes first when view_count is equal
        assert ids.index(second.id) < ids.index(first.id)


# ---------------------------------------------------------------------------
# EventQuerySet.ending_within_days
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEndingWithinDays:
    """Behavior tests for EventQuerySet.ending_within_days(days, today=today).

    Selection rule: published ongoing events whose end_date is between today
    (inclusive) and today+days (inclusive), ordered soonest-first.
    """

    def test_end_date_today_plus_5_is_included(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+5",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id in list(qs.values_list("id", flat=True))

    def test_end_date_today_plus_6_is_excluded(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+6",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=6),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id not in list(qs.values_list("id", flat=True))

    def test_end_date_today_is_included(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+0",
            start_date=today - timedelta(days=3),
            end_date=today,
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id in list(qs.values_list("id", flat=True))

    def test_end_date_yesterday_is_excluded(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="Ended yesterday",
            start_date=today - timedelta(days=5),
            end_date=today - timedelta(days=1),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id not in list(qs.values_list("id", flat=True))

    def test_upcoming_event_within_window_is_excluded(self, make_event):
        """start_date > today means the event has not started yet; must be excluded."""
        today = date(2026, 6, 26)
        event = make_event(
            title="Not started yet",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id not in list(qs.values_list("id", flat=True))

    def test_draft_within_window_is_excluded(self, make_event):
        """Draft events must not appear even if end_date is within the window."""
        today = date(2026, 6, 26)
        event = make_event(
            title="Draft event",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=3),
            publish_status=Event.PublishStatus.DRAFT,
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id not in list(qs.values_list("id", flat=True))

    def test_ordering_is_by_end_date_ascending(self, make_event):
        today = date(2026, 6, 26)
        later = make_event(
            title="Later",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=4),
        )
        sooner = make_event(
            title="Sooner",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=2),
        )
        qs = list(Event.objects.published().ending_within_days(5, today=today))
        ids = [e.id for e in qs]
        assert ids.index(sooner.id) < ids.index(later.id)


# ---------------------------------------------------------------------------
# list_staff_events (PR-E1 — staff quality-warning drilldown)
#
# warning drilldowns must return exactly the same population the matching
# count_published_* function counts (dashboard drilldown parity). Unknown/
# blank warning values are ignored (fallback to no warning filter), mirroring
# the existing selected_status normalisation pattern in staff views.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListStaffEvents:
    def test_no_filters_returns_all_events_regardless_of_publish_status(
        self, make_event, make_draft_event
    ):
        from events.queries import list_staff_events

        published = make_event(official_url="https://example.com/a")
        draft = make_draft_event(official_url="https://example.com/b")

        result = list_staff_events()

        ids = {e.id for e in result}
        assert ids == {published.id, draft.id}

    def test_ordered_by_created_at_descending(self, make_event):
        from events.queries import list_staff_events

        older = make_event(title="older")
        newer = make_event(title="newer")

        result = list(list_staff_events())

        assert [e.id for e in result] == [newer.id, older.id]

    def test_publish_status_filter_restricts_to_that_status(
        self, make_event, make_draft_event
    ):
        from events.queries import list_staff_events
        from events.models import Event

        published = make_event(official_url="https://example.com/a")
        make_draft_event(official_url="https://example.com/b")

        result = list_staff_events(publish_status=Event.PublishStatus.PUBLISHED)

        assert [e.id for e in result] == [published.id]

    def test_unknown_publish_status_is_ignored(self, make_event):
        from events.queries import list_staff_events

        event = make_event(official_url="https://example.com/a")

        result = list_staff_events(publish_status="not-a-real-status")

        assert [e.id for e in result] == [event.id]

    @pytest.mark.parametrize(
        "warning,setup_kwargs",
        [
            ("missing_official_url", {"official_url": None}),
            (
                "missing_dates",
                {
                    "official_url": "https://example.com/dates",
                    "start_date": None,
                    "end_date": None,
                },
            ),
            ("missing_region", {"official_url": "https://example.com/region", "region": ""}),
        ],
    )
    def test_warning_filter_matches_matching_event_and_excludes_clean_event(
        self, make_event, warning, setup_kwargs
    ):
        from events.queries import list_staff_events

        matching = make_event(**setup_kwargs)
        clean = make_event(
            official_url=f"https://example.com/clean-{warning}",
            region="서울",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
        )

        result = list_staff_events(warning=warning)

        ids = {e.id for e in result}
        assert matching.id in ids
        assert clean.id not in ids

    def test_missing_poster_warning_matches_matching_event_and_excludes_clean_event(
        self, make_event, png_bytes, settings, tmp_path
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from events.queries import list_staff_events

        settings.MEDIA_ROOT = str(tmp_path)
        matching = make_event(official_url="https://example.com/poster-missing")
        clean = make_event(official_url="https://example.com/poster-present")
        clean.poster_image = SimpleUploadedFile(
            "poster.png", png_bytes(), content_type="image/png"
        )
        clean.save()

        result = list_staff_events(warning="missing_poster")

        ids = {e.id for e in result}
        assert matching.id in ids
        assert clean.id not in ids

    def test_ended_still_published_warning_uses_today_override(self, make_event):
        from events.queries import list_staff_events

        today = date(2020, 6, 15)
        ended = make_event(
            official_url="https://example.com/ended",
            end_date=today - timedelta(days=1),
        )
        not_ended = make_event(
            official_url="https://example.com/not-ended",
            end_date=today + timedelta(days=1),
        )

        result = list_staff_events(warning="ended_still_published", today=today)

        ids = {e.id for e in result}
        assert ended.id in ids
        assert not_ended.id not in ids

    def test_warning_filter_excludes_draft_events_even_if_matching(
        self, make_draft_event
    ):
        """Warning drilldowns are published-scoped, matching count_published_*."""
        from events.queries import list_staff_events

        make_draft_event(official_url=None)

        result = list_staff_events(warning="missing_official_url")

        assert list(result) == []

    def test_unknown_warning_is_ignored(self, make_event, make_draft_event):
        from events.queries import list_staff_events

        published = make_event(official_url="https://example.com/a")
        draft = make_draft_event(official_url="https://example.com/b")

        result = list_staff_events(warning="not-a-real-warning")

        ids = {e.id for e in result}
        assert ids == {published.id, draft.id}

    def test_warning_count_matches_count_published_function(self, make_event, make_draft_event):
        """Drilldown row count must equal the dashboard's count_published_* value."""
        from events.queries import count_published_missing_region, list_staff_events

        make_event(official_url="https://example.com/a", region="")
        make_event(official_url="https://example.com/b", region="")
        make_draft_event(official_url="https://example.com/c", region="")

        result = list_staff_events(warning="missing_region")

        assert result.count() == count_published_missing_region()
