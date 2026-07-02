"""Tests for events.queries quality-warning counters (staff dashboard PR-1b).

All counters are scoped to Event.objects.published() only. Each predicate is
an independent per-column check (one event can trip multiple warnings), so
there is no if/elif classification anywhere here or in the implementation.
"""
from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from events.queries import (
    count_published_ended_still_published,
    count_published_missing_dates,
    count_published_missing_official_url,
    count_published_missing_poster,
    count_published_missing_region,
    published_quality_warnings,
)


# ---------------------------------------------------------------------------
# count_published_missing_official_url
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCountPublishedMissingOfficialUrl:
    def test_null_official_url_is_counted(self, make_event):
        make_event(official_url=None)

        assert count_published_missing_official_url() == 1

    def test_blank_official_url_is_counted(self, make_event):
        make_event(official_url="")

        assert count_published_missing_official_url() == 1

    def test_present_official_url_is_not_counted(self, make_event):
        make_event(official_url="https://example.com/a")

        assert count_published_missing_official_url() == 0

    def test_non_published_excluded(self, make_draft_event):
        make_draft_event(official_url=None)

        assert count_published_missing_official_url() == 0

    def test_zero_when_none(self):
        assert count_published_missing_official_url() == 0

    def test_mixed_null_and_present_only_null_counted(self, make_event):
        make_event(official_url=None)
        make_event(official_url="https://example.com/b")

        assert count_published_missing_official_url() == 1

    def test_two_matching_events_counts_two(self, make_event):
        # Guards against a .count() -> .exists() regression: bool is a
        # subclass of int, so an exists()-based count would still pass the
        # 0/1 assertions above but silently break on N>=2.
        # official_url is unique, so use NULL for both (NULLs don't collide;
        # two "" would raise a UNIQUE IntegrityError).
        make_event(official_url=None)
        make_event(official_url=None)

        assert count_published_missing_official_url() == 2


# ---------------------------------------------------------------------------
# count_published_ended_still_published
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCountPublishedEndedStillPublished:
    def test_end_date_before_today_is_counted(self, make_event):
        today = date(2020, 6, 15)
        make_event(end_date=today - timedelta(days=1))

        assert count_published_ended_still_published(today=today) == 1

    def test_end_date_equal_today_is_not_counted(self, make_event):
        today = date(2020, 6, 15)
        make_event(end_date=today)

        assert count_published_ended_still_published(today=today) == 0

    def test_end_date_after_today_is_not_counted(self, make_event):
        today = date(2020, 6, 15)
        make_event(end_date=today + timedelta(days=1))

        assert count_published_ended_still_published(today=today) == 0

    def test_null_end_date_is_not_counted_and_does_not_crash(self, make_event):
        today = date(2020, 6, 15)
        make_event(end_date=None)

        assert count_published_ended_still_published(today=today) == 0

    def test_non_published_ended_excluded(self, make_draft_event):
        today = date(2020, 6, 15)
        make_draft_event(end_date=today - timedelta(days=1))

        assert count_published_ended_still_published(today=today) == 0

    def test_zero_when_none(self):
        today = date(2020, 6, 15)

        assert count_published_ended_still_published(today=today) == 0

    def test_default_today_returns_int_without_crash(self, make_event):
        make_event(end_date=date(2000, 1, 1))

        result = count_published_ended_still_published()

        assert isinstance(result, int)

    def test_two_matching_events_counts_two(self, make_event):
        # Guards against a .count() -> .exists() regression (bool is a
        # subclass of int; an exists()-based count would still pass 0/1).
        today = date(2020, 6, 15)
        make_event(end_date=today - timedelta(days=1))
        make_event(end_date=today - timedelta(days=2))

        assert count_published_ended_still_published(today=today) == 2


# ---------------------------------------------------------------------------
# count_published_missing_poster
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCountPublishedMissingPoster:
    def test_blank_poster_is_counted(self, make_event):
        make_event(official_url=None)

        assert count_published_missing_poster() == 1

    def test_set_poster_image_is_not_counted(self, make_event, png_bytes, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        event = make_event(official_url=None)
        event.poster_image = SimpleUploadedFile(
            "poster.png", png_bytes(), content_type="image/png"
        )
        event.save()

        assert count_published_missing_poster() == 0

    def test_non_published_excluded(self, make_draft_event):
        make_draft_event(official_url=None)

        assert count_published_missing_poster() == 0

    def test_zero_when_none(self):
        assert count_published_missing_poster() == 0

    def test_two_matching_events_counts_two(self, make_event):
        # Guards against a .count() -> .exists() regression (bool is a
        # subclass of int; an exists()-based count would still pass 0/1).
        make_event(official_url=None)
        make_event(official_url="https://example.com/other")

        assert count_published_missing_poster() == 2


# ---------------------------------------------------------------------------
# count_published_missing_dates
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCountPublishedMissingDates:
    def test_null_start_date_is_counted(self, make_event):
        make_event(official_url=None, start_date=None, end_date=date(2020, 1, 1))

        assert count_published_missing_dates() == 1

    def test_null_end_date_is_counted(self, make_event):
        make_event(official_url=None, start_date=date(2020, 1, 1), end_date=None)

        assert count_published_missing_dates() == 1

    def test_both_dates_set_is_not_counted(self, make_event):
        make_event(
            official_url=None, start_date=date(2020, 1, 1), end_date=date(2020, 1, 2)
        )

        assert count_published_missing_dates() == 0

    def test_both_dates_null_counted_exactly_once(self, make_event):
        make_event(official_url=None, start_date=None, end_date=None)

        assert count_published_missing_dates() == 1

    def test_non_published_excluded(self, make_draft_event):
        make_draft_event(official_url=None, start_date=None, end_date=None)

        assert count_published_missing_dates() == 0

    def test_zero_when_none(self, make_event):
        make_event(
            official_url=None, start_date=date(2020, 1, 1), end_date=date(2020, 1, 2)
        )

        assert count_published_missing_dates() == 0

    def test_two_matching_events_counts_two(self, make_event):
        # Guards against a .count() -> .exists() regression (bool is a
        # subclass of int; an exists()-based count would still pass 0/1).
        make_event(official_url=None, start_date=None, end_date=date(2020, 1, 1))
        make_event(
            official_url="https://example.com/other", start_date=None, end_date=None
        )

        assert count_published_missing_dates() == 2


# ---------------------------------------------------------------------------
# count_published_missing_region
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCountPublishedMissingRegion:
    def test_blank_region_is_counted(self, make_event):
        make_event(official_url=None, region="")

        assert count_published_missing_region() == 1

    def test_present_region_is_not_counted(self, make_event):
        make_event(official_url=None, region="서울")

        assert count_published_missing_region() == 0

    def test_whitespace_only_region_is_not_counted(self, make_event):
        # Conscious v1 decision: no strip/normalization. A whitespace-only
        # region is technically "blank" to a human, but this counter only
        # checks region == "" exactly, so it is NOT counted.
        make_event(official_url=None, region=" ")

        assert count_published_missing_region() == 0

    def test_non_published_excluded(self, make_draft_event):
        make_draft_event(official_url=None, region="")

        assert count_published_missing_region() == 0

    def test_zero_when_none(self, make_event):
        make_event(official_url=None, region="서울")

        assert count_published_missing_region() == 0

    def test_two_matching_events_counts_two(self, make_event):
        # Guards against a .count() -> .exists() regression (bool is a
        # subclass of int; an exists()-based count would still pass 0/1).
        make_event(official_url=None, region="")
        make_event(official_url="https://example.com/other", region="")

        assert count_published_missing_region() == 2


# ---------------------------------------------------------------------------
# published_quality_warnings (composite)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPublishedQualityWarnings:
    def test_all_five_keys_present_and_zero_on_empty_db(self):
        result = published_quality_warnings()

        assert result == {
            "missing_official_url": 0,
            "ended_still_published": 0,
            "missing_poster": 0,
            "missing_dates": 0,
            "missing_region": 0,
            "total": 0,
        }
        for value in result.values():
            assert isinstance(value, int)

    def test_total_is_sum_of_the_five_warning_counts(self, make_event):
        make_event(official_url=None, region="")

        result = published_quality_warnings()

        assert result["total"] == (
            result["missing_official_url"]
            + result["ended_still_published"]
            + result["missing_poster"]
            + result["missing_dates"]
            + result["missing_region"]
        )

    def test_event_tripping_two_predicates_contributes_two_to_total(
        self, make_event, png_bytes, settings, tmp_path
    ):
        # official_url and region both missing on the same event, with every
        # other predicate deliberately kept clean: this is a sum-of-flags
        # total, not a distinct-event count, so it contributes exactly 2.
        settings.MEDIA_ROOT = str(tmp_path)
        today = date(2020, 6, 15)
        event = make_event(
            official_url=None,
            region="",
            start_date=date(2020, 1, 1),
            end_date=today + timedelta(days=30),
        )
        event.poster_image = SimpleUploadedFile(
            "poster.png", png_bytes(), content_type="image/png"
        )
        event.save()

        result = published_quality_warnings(today=today)

        assert result["total"] == 2

    def test_independent_counts_no_cross_contamination(self, make_event, png_bytes, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        today = date(2020, 6, 15)
        future_end = today + timedelta(days=30)

        def _with_poster(event):
            event.poster_image = SimpleUploadedFile(
                "poster.png", png_bytes(), content_type="image/png"
            )
            event.save()
            return event

        # Each event trips exactly one predicate; every other predicate on it
        # is deliberately kept "clean" so the 5 counts stay independent.
        _with_poster(
            make_event(
                official_url=None,
                region="서울",
                start_date=date(2020, 1, 1),
                end_date=future_end,
            )
        )
        _with_poster(
            make_event(
                official_url="https://example.com/ended",
                region="서울",
                start_date=date(2020, 1, 1),
                end_date=today - timedelta(days=1),
            )
        )
        make_event(
            official_url="https://example.com/poster",
            region="서울",
            start_date=date(2020, 1, 1),
            end_date=future_end,
        )  # left without a poster on purpose
        _with_poster(
            make_event(
                official_url="https://example.com/dates",
                region="서울",
                start_date=None,
                end_date=future_end,
            )
        )
        _with_poster(
            make_event(
                official_url="https://example.com/region",
                region="",
                start_date=date(2020, 1, 1),
                end_date=future_end,
            )
        )

        result = published_quality_warnings(today=today)

        assert result == {
            "missing_official_url": 1,
            "ended_still_published": 1,
            "missing_poster": 1,
            "missing_dates": 1,
            "missing_region": 1,
            "total": 5,
        }

    def test_one_event_tripping_two_predicates_counts_in_both_keys(self, make_event):
        make_event(official_url=None, region="")

        result = published_quality_warnings()

        assert result["missing_official_url"] == 1
        assert result["missing_region"] == 1

    def test_non_published_event_tripping_all_counts_zero(self, make_draft_event):
        today = date(2020, 6, 15)
        make_draft_event(
            official_url=None,
            region="",
            start_date=None,
            end_date=today - timedelta(days=1),
        )

        result = published_quality_warnings(today=today)

        assert result == {
            "missing_official_url": 0,
            "ended_still_published": 0,
            "missing_poster": 0,
            "missing_dates": 0,
            "missing_region": 0,
            "total": 0,
        }

    def test_today_is_forwarded_to_ended_check(self, make_event):
        fixed_today = date(2020, 1, 1)
        make_event(
            official_url="https://example.com/x",
            region="서울",
            start_date=date(2019, 1, 1),
            end_date=date(2019, 12, 31),  # ended relative to fixed_today only
        )

        result = published_quality_warnings(today=fixed_today)

        assert result["ended_still_published"] == 1
