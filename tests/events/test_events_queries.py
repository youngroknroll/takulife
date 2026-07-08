"""Tests for events/queries.py: listing parameters, published-event listing.

Covers:
- parse_public_listing_params: filtering, validation, blank-string handling
- list_published_events: ordering and status filtering with a fixed today
- PUBLIC_LISTING_PAGE_SIZE: page size constant
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
# PUBLIC_LISTING_PAGE_SIZE constant
# ---------------------------------------------------------------------------

class TestPublicListingPageSize:
    def test_page_size_constant_is_10(self):
        from events.queries import PUBLIC_LISTING_PAGE_SIZE

        assert PUBLIC_LISTING_PAGE_SIZE == 10


# ---------------------------------------------------------------------------
# with_public_status queryset arms (moved from tests/core/test_coverage_supplements.py)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWithPublicStatus:
    def test_with_public_status_ended(self, make_event):
        today = date(2026, 7, 1)
        ended = make_event(
            title="끝난 행사",
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=1),
        )
        ongoing = make_event(
            title="진행 행사",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )

        result = Event.objects.published().with_public_status("ended", today=today)

        assert ended in result
        assert ongoing not in result

    def test_with_public_status_unknown_returns_unfiltered(self, make_event):
        today = date(2026, 7, 1)
        make_event(title="아무 행사")
        qs = Event.objects.published()

        # Unrecognised status falls through every arm to `return self`.
        assert list(qs.with_public_status("nonsense", today=today)) == list(qs)