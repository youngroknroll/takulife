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
# Helpers
# ---------------------------------------------------------------------------

def make_event(**kwargs):
    defaults = {"title": "Test Event", "publish_status": Event.PublishStatus.PUBLISHED}
    defaults.update(kwargs)
    return Event.objects.create(**defaults)


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
        assert result["region"] == "seoul"
        assert result["category"] == "popup_store"
        assert result["work_title"] == "Gundam"
        assert result["start_date_from"] == date(2026, 6, 1)
        assert result["start_date_to"] == date(2026, 6, 30)
        assert result["status"] == "upcoming"

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


# ---------------------------------------------------------------------------
# list_published_events
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestListPublishedEvents:
    def test_returns_only_published_events(self):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        published = make_event(title="Published")
        make_event(title="Draft", publish_status=Event.PublishStatus.DRAFT)

        qs = list_published_events({}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert published.id in ids
        assert len(ids) == 1

    def test_filters_by_status_upcoming(self):
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

    def test_filters_by_status_ongoing(self):
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

    def test_default_order_ongoing_then_upcoming_then_ended(self):
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

    def test_uses_today_default_via_localdate_when_not_provided(self):
        """When today is omitted, the function still returns a queryset."""
        from events.queries import list_published_events

        make_event(title="Any event")
        qs = list_published_events({})
        assert qs.count() == 1


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
    def test_page_size_constant_is_20(self):
        from events.queries import PUBLIC_LISTING_PAGE_SIZE

        assert PUBLIC_LISTING_PAGE_SIZE == 20
