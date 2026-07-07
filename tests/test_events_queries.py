"""Tests for events/queries.py and events/presenters.py.

Covers:
- parse_public_listing_params: filtering, validation, blank-string handling
- list_published_events: ordering and status filtering with a fixed today
- derive_event_display: status classification, closing_soon boundary, dday, null dates
"""
import pytest
from datetime import date, timedelta

from events.models import Event


# ---------------------------------------------------------------------------
# parse_public_listing_params
# ---------------------------------------------------------------------------

class TestParsePublicListingParams:
    def test_accepts_all_allowed_fields(self):
        from events.queries import parse_public_listing_params

        raw = {
            "q": "popup",
            "region": "seoul",
            "category": "popup_store",
            "work_title": "Gundam",
            "start_date_from": "2026-06-01",
            "start_date_to": "2026-06-30",
            "status": "upcoming",
        }
        result = parse_public_listing_params(raw)
        assert result["q"] == "popup"
        # region/category are multi-value: a single value normalises to a 1-list
        assert result["region"] == ["seoul"]
        assert result["category"] == ["popup_store"]
        assert result["work_title"] == "Gundam"
        assert result["start_date_from"] == date(2026, 6, 1)
        assert result["start_date_to"] == date(2026, 6, 30)
        assert result["status"] == "upcoming"

    def test_collects_multiple_region_and_category_values(self):
        from django.http import QueryDict
        from events.queries import parse_public_listing_params

        raw = QueryDict(
            "region=seoul&region=gyeonggi&category=popup_store&category=exhibition"
        )
        result = parse_public_listing_params(raw)
        assert result["region"] == ["seoul", "gyeonggi"]
        assert result["category"] == ["popup_store", "exhibition"]

    def test_drops_unknown_keys(self):
        from events.queries import parse_public_listing_params

        raw = {"q": "popup", "unknown_key": "should_be_dropped", "another": "also_dropped"}
        result = parse_public_listing_params(raw)
        assert "unknown_key" not in result
        assert "another" not in result
        assert result["q"] == "popup"

    def test_drops_page_key(self):
        from events.queries import parse_public_listing_params

        raw = {"page": "2", "q": "test"}
        result = parse_public_listing_params(raw)
        assert "page" not in result

    def test_validates_status_choice(self):
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"status": "invalid_status"})
        assert "status" in str(exc_info.value.detail)

    def test_rejects_bad_date_format(self):
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"start_date_from": "2026/06/01"})
        assert "start_date_from" in str(exc_info.value.detail)

    def test_rejects_bad_start_date_to_format(self):
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"start_date_to": "06-01-2026"})
        assert "start_date_to" in str(exc_info.value.detail)

    def test_ignores_blank_string_for_q(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"q": ""})
        # blank strings are accepted as valid (allow_blank=True) but the queryset
        # layer does not filter on them — validated_data will contain the key with ""
        # The querysets.py filter_for_public_listing skips blank values via truthiness check.
        assert result.get("q", "") == ""

    def test_ignores_blank_string_for_region(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"region": ""})
        assert result.get("region", "") == ""

    def test_ignores_blank_string_for_category(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"category": ""})
        assert result.get("category", "") == ""

    def test_ignores_blank_string_for_work_title(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"work_title": ""})
        assert result.get("work_title", "") == ""

    def test_empty_params_returns_empty_dict(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({})
        assert result == {}

    def test_accepts_dict_like_mapping(self):
        """Should accept any Mapping, not just DRF QueryDict."""
        from events.queries import parse_public_listing_params

        raw = {"q": "test"}
        result = parse_public_listing_params(raw)
        assert result["q"] == "test"

    def test_accepts_sort_choice(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"sort": "closing_soon"})
        assert result["sort"] == "closing_soon"

    def test_rejects_invalid_sort_choice(self):
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"sort": "not_a_real_sort"})
        assert "sort" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# list_published_events
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestListPublishedEvents:
    def test_returns_only_published_events(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        published = make_event(title="Published")
        make_event(title="Draft", publish_status=Event.PublishStatus.DRAFT)

        qs = list_published_events({}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert published.id in ids
        assert len(ids) == 1

    def test_filters_by_status_upcoming(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        upcoming = make_event(
            title="Upcoming",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        make_event(
            title="Ongoing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
        )

        qs = list_published_events({"status": "upcoming"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert [upcoming.id] == ids

    def test_filters_by_status_ongoing(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        ongoing = make_event(
            title="Ongoing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
        )
        make_event(
            title="Upcoming",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=5),
        )

        qs = list_published_events({"status": "ongoing"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ongoing.id in ids
        assert len(ids) == 1

    def test_default_order_ongoing_then_upcoming_then_ended(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        ended = make_event(
            title="Ended",
            start_date=today - timedelta(days=5),
            end_date=today - timedelta(days=1),
        )
        upcoming = make_event(
            title="Upcoming",
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=4),
        )
        ongoing = make_event(
            title="Ongoing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=2),
        )

        qs = list_published_events({}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids.index(ongoing.id) < ids.index(upcoming.id)
        assert ids.index(upcoming.id) < ids.index(ended.id)

    def test_uses_today_default_via_localdate_when_not_provided(self, make_event):
        """When today is omitted, the function still returns a queryset."""
        from events.queries import list_published_events

        make_event(title="Any event")
        qs = list_published_events({})
        assert qs.count() == 1

    def test_sort_closing_soon_orders_not_ended_events_first_ascending_nulls_last(self, make_event):
        """Closing-soon sort ranks not-yet-ended events (end_date null or >= today)
        first, soonest-ending first (nulls last). Already-ended events are pushed
        to the back — see test_sort_closing_soon_never_surfaces_ended_event_at_top
        for the regression this guards against."""
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        no_end = make_event(title="No end", start_date=today, end_date=None)
        ongoing = make_event(
            title="Ongoing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        upcoming = make_event(
            title="Upcoming",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=20),
        )
        ended = make_event(
            title="Ended",
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=2),
        )

        qs = list_published_events({"sort": "closing_soon"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids == [ongoing.id, upcoming.id, no_end.id, ended.id]

    def test_sort_closing_soon_never_surfaces_ended_event_at_top(self, make_event):
        """Regression guard: an event that ended long ago (smallest end_date)
        must never rank above a currently-ongoing event under closing_soon sort."""
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        long_ended = make_event(
            title="Long ended",
            start_date=today - timedelta(days=100),
            end_date=today - timedelta(days=90),
        )
        ongoing = make_event(
            title="Ongoing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=3),
        )

        qs = list_published_events({"sort": "closing_soon"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids[0] == ongoing.id
        assert ids.index(ongoing.id) < ids.index(long_ended.id)

    def test_sort_closing_soon_ended_group_orders_most_recently_ended_first(self, make_event):
        """Within the already-ended group, most-recently-ended sorts first."""
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        ended_long_ago = make_event(
            title="Ended long ago",
            start_date=today - timedelta(days=100),
            end_date=today - timedelta(days=90),
        )
        ended_recently = make_event(
            title="Ended recently",
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=1),
        )

        qs = list_published_events({"sort": "closing_soon"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids == [ended_recently.id, ended_long_ago.id]

    def test_sort_closing_soon_tiebreaks_by_id(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        end_date = today + timedelta(days=5)
        first = make_event(title="First", start_date=today, end_date=end_date)
        second = make_event(title="Second", start_date=today, end_date=end_date)

        qs = list_published_events({"sort": "closing_soon"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids.index(first.id) < ids.index(second.id)

    def test_sort_start_asc_orders_by_start_date_ascending(self, make_event):
        """start_asc sort must order purely by start_date, ignoring the default
        ongoing/upcoming/ended state ranking (ended has the earliest start_date
        here but ranks last under the default order_for_public_listing)."""
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        ended = make_event(
            title="Ended",
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=5),
        )
        ongoing = make_event(
            title="Ongoing",
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=3),
        )
        upcoming = make_event(
            title="Upcoming",
            start_date=today + timedelta(days=5),
            end_date=today + timedelta(days=10),
        )

        qs = list_published_events({"sort": "start_asc"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids == [ended.id, ongoing.id, upcoming.id]

    def test_sort_start_asc_tiebreaks_by_id(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        start_date = today + timedelta(days=1)
        first = make_event(title="First", start_date=start_date, end_date=today + timedelta(days=10))
        second = make_event(title="Second", start_date=start_date, end_date=today + timedelta(days=10))

        qs = list_published_events({"sort": "start_asc"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids.index(first.id) < ids.index(second.id)

    def test_sort_newest_orders_by_id_descending(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        first = make_event(title="First", start_date=today, end_date=today + timedelta(days=5))
        second = make_event(title="Second", start_date=today, end_date=today + timedelta(days=5))

        qs = list_published_events({"sort": "newest"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids == [second.id, first.id]

    def test_no_sort_param_keeps_default_ordering(self, make_event):
        """Regression guard: omitting sort must not change the existing default order."""
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        ended = make_event(
            title="Ended",
            start_date=today - timedelta(days=5),
            end_date=today - timedelta(days=1),
        )
        upcoming = make_event(
            title="Upcoming",
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=4),
        )
        ongoing = make_event(
            title="Ongoing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=2),
        )

        qs_no_sort = list_published_events({}, today=today)
        qs_explicit_default = list_published_events({}, today=today)
        assert list(qs_no_sort.values_list("id", flat=True)) == list(
            qs_explicit_default.values_list("id", flat=True)
        )
        ids = list(qs_no_sort.values_list("id", flat=True))
        assert ids.index(ongoing.id) < ids.index(upcoming.id)
        assert ids.index(upcoming.id) < ids.index(ended.id)


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
# PUBLIC_LISTING_PAGE_SIZE constant
# ---------------------------------------------------------------------------

class TestPublicListingPageSize:
    def test_page_size_constant_is_10(self):
        from events.queries import PUBLIC_LISTING_PAGE_SIZE

        assert PUBLIC_LISTING_PAGE_SIZE == 10


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
