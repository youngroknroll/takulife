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

@pytest.mark.unit
class TestDeriveEventDisplay:
    def test_시작_예정일_전이면_상태는_예정이고_디데이는_시작까지_남은_일수다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today + timedelta(days=3), end_date=today + timedelta(days=10))
        result = derive_event_display(event, today=today)

        assert result["status"] == "upcoming"
        assert result["dday"] == 3  # days to start

    def test_진행_기간_중이면_상태는_진행중이고_디데이는_종료까지_남은_일수다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=2), end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert result["status"] == "ongoing"
        assert result["dday"] == 5  # days to end

    def test_종료일이_4일_후면_마감임박_상태로_분류된다(self):
        """end_date == today + 4 days is exactly within the closing_soon window."""
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=1), end_date=today + timedelta(days=4))
        result = derive_event_display(event, today=today)

        assert result["status"] == "closing_soon"
        assert result["dday"] == 4

    def test_종료일이_오늘이면_마감임박_상태로_분류된다(self):
        """end_date == today is also closing_soon (ends today)."""
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=2), end_date=today)
        result = derive_event_display(event, today=today)

        assert result["status"] == "closing_soon"
        assert result["dday"] == 0

    def test_종료일이_5일_후면_마감임박이_아닌_진행중_상태로_분류된다(self):
        """end_date == today + 5 days is ongoing, NOT closing_soon."""
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=1), end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert result["status"] == "ongoing"
        assert result["dday"] == 5

    def test_종료일이_지났으면_상태는_종료이고_디데이는_없다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=10), end_date=today - timedelta(days=1))
        result = derive_event_display(event, today=today)

        assert result["status"] == "ended"
        assert result["dday"] is None

    def test_시작일이_없으면_상태와_디데이_모두_None이다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=None, end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert result["status"] is None
        assert result["dday"] is None

    def test_종료일이_없으면_상태와_디데이_모두_None이다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=1), end_date=None)
        result = derive_event_display(event, today=today)

        assert result["status"] is None
        assert result["dday"] is None

    def test_시작일과_종료일이_모두_없어도_오류_없이_None을_반환한다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=None, end_date=None)
        result = derive_event_display(event, today=today)

        assert result["status"] is None
        assert result["dday"] is None

    def test_기준일을_생략해도_결과_딕셔너리를_반환한다(self):
        """When today is not provided, the function still returns a result dict."""
        from events.presenters import derive_event_display

        event = Event(start_date=None, end_date=None)
        result = derive_event_display(event)

        assert "status" in result
        assert "dday" in result

    def test_반환값에는_상태와_디데이_키가_모두_포함된다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today + timedelta(days=1), end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert "status" in result
        assert "dday" in result


# ---------------------------------------------------------------------------
# most_viewed queryset method
# ---------------------------------------------------------------------------

@pytest.mark.domain
@pytest.mark.django_db
class TestMostViewed:
    def test_조회수_내림차순으로_행사를_정렬해_반환한다(self, make_event):
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

    def test_지정한_limit_개수를_넘지_않게_반환한다(self, make_event):
        for i in range(7):
            make_event(title=f"Event {i}")

        result = list(Event.objects.published().most_viewed(5))
        assert len(result) <= 5

    def test_조회수가_높아도_초안_행사는_제외한다(self, make_event):
        published = make_event(title="Published")
        draft = make_event(title="Draft", publish_status=Event.PublishStatus.DRAFT)
        Event.objects.filter(pk=draft.pk).update(view_count=999)

        result = list(Event.objects.published().most_viewed(5))
        ids = [e.id for e in result]
        assert draft.id not in ids
        assert published.id in ids

    def test_조회수가_같으면_id_내림차순으로_정렬한다(self, make_event):
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

@pytest.mark.domain
@pytest.mark.django_db
class TestEndingWithinDays:
    """Behavior tests for EventQuerySet.ending_within_days(days, today=today).

    Selection rule: published ongoing events whose end_date is between today
    (inclusive) and today+days (inclusive), ordered soonest-first.
    """

    def test_종료일이_오늘로부터_5일_후면_포함된다(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+5",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id in list(qs.values_list("id", flat=True))

    def test_종료일이_오늘로부터_6일_후면_제외된다(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+6",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=6),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id not in list(qs.values_list("id", flat=True))

    def test_종료일이_오늘이면_포함된다(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+0",
            start_date=today - timedelta(days=3),
            end_date=today,
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id in list(qs.values_list("id", flat=True))

    def test_종료일이_어제면_제외된다(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="Ended yesterday",
            start_date=today - timedelta(days=5),
            end_date=today - timedelta(days=1),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id not in list(qs.values_list("id", flat=True))

    def test_아직_시작하지_않은_행사는_종료일이_창_안에_있어도_제외된다(self, make_event):
        """start_date > today means the event has not started yet; must be excluded."""
        today = date(2026, 6, 26)
        event = make_event(
            title="Not started yet",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id not in list(qs.values_list("id", flat=True))

    def test_초안_행사는_종료일이_창_안에_있어도_제외된다(self, make_event):
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

    def test_종료일_오름차순으로_정렬한다(self, make_event):
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


@pytest.mark.domain
@pytest.mark.django_db
class TestListStaffEvents:
    def test_필터가_없으면_게시_상태와_무관하게_모든_행사를_반환한다(
        self, make_event, make_draft_event
    ):
        from events.queries import list_staff_events

        published = make_event(official_url="https://example.com/a")
        draft = make_draft_event(official_url="https://example.com/b")

        result = list_staff_events()

        ids = {e.id for e in result}
        assert ids == {published.id, draft.id}

    def test_생성일_내림차순으로_정렬한다(self, make_event):
        from events.queries import list_staff_events

        older = make_event(title="older")
        newer = make_event(title="newer")

        result = list(list_staff_events())

        assert [e.id for e in result] == [newer.id, older.id]

    def test_게시_상태_필터를_지정하면_해당_상태의_행사만_반환한다(
        self, make_event, make_draft_event
    ):
        from events.queries import list_staff_events
        from events.models import Event

        published = make_event(official_url="https://example.com/a")
        make_draft_event(official_url="https://example.com/b")

        result = list_staff_events(publish_status=Event.PublishStatus.PUBLISHED)

        assert [e.id for e in result] == [published.id]

    def test_알_수_없는_게시_상태_필터는_무시하고_전체를_반환한다(self, make_event):
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
        ids=["공식_URL_누락", "날짜_누락", "지역_누락"],
    )
    def test_경고_필터는_해당_경고에_해당하는_행사만_포함하고_정상_행사는_제외한다(
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

    def test_포스터_누락_경고_필터는_포스터_없는_행사만_포함하고_있는_행사는_제외한다(
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

    def test_종료됐지만_게시중_경고_필터는_기준일_인자_기준으로_판정한다(self, make_event):
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

    def test_경고_조건에_맞아도_초안_행사는_경고_필터_결과에서_제외된다(
        self, make_draft_event
    ):
        """Warning drilldowns are published-scoped, matching count_published_*."""
        from events.queries import list_staff_events

        make_draft_event(official_url=None)

        result = list_staff_events(warning="missing_official_url")

        assert list(result) == []

    def test_알_수_없는_경고_필터는_무시하고_전체를_반환한다(self, make_event, make_draft_event):
        from events.queries import list_staff_events

        published = make_event(official_url="https://example.com/a")
        draft = make_draft_event(official_url="https://example.com/b")

        result = list_staff_events(warning="not-a-real-warning")

        ids = {e.id for e in result}
        assert ids == {published.id, draft.id}

    def test_경고_필터_결과_건수는_대시보드_집계_함수의_값과_일치한다(self, make_event, make_draft_event):
        """Drilldown row count must equal the dashboard's count_published_* value."""
        from events.queries import count_published_missing_region, list_staff_events

        make_event(official_url="https://example.com/a", region="")
        make_event(official_url="https://example.com/b", region="")
        make_draft_event(official_url="https://example.com/c", region="")

        result = list_staff_events(warning="missing_region")

        assert result.count() == count_published_missing_region()
