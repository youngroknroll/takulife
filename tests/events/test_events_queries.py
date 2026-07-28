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

@pytest.mark.unit
class TestParsePublicListingParams:
    def test_허용된_모든_필드를_받아들여_파싱한다(self):
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

    def test_지역과_카테고리는_여러_값을_리스트로_모은다(self):
        from django.http import QueryDict
        from events.queries import parse_public_listing_params

        raw = QueryDict(
            "region=seoul&region=gyeonggi&category=popup_store&category=exhibition"
        )
        result = parse_public_listing_params(raw)
        assert result["region"] == ["seoul", "gyeonggi"]
        assert result["category"] == ["popup_store", "exhibition"]

    def test_알_수_없는_키는_결과에서_제외한다(self):
        from events.queries import parse_public_listing_params

        raw = {"q": "popup", "unknown_key": "should_be_dropped", "another": "also_dropped"}
        result = parse_public_listing_params(raw)
        assert "unknown_key" not in result
        assert "another" not in result
        assert result["q"] == "popup"

    def test_페이지_번호_키는_결과에서_제외한다(self):
        from events.queries import parse_public_listing_params

        raw = {"page": "2", "q": "test"}
        result = parse_public_listing_params(raw)
        assert "page" not in result

    def test_잘못된_상태_값은_거부한다(self):
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"status": "invalid_status"})
        assert "status" in str(exc_info.value.detail)

    def test_잘못된_형식의_시작일_이후_값을_거부한다(self):
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"start_date_from": "2026/06/01"})
        assert "start_date_from" in str(exc_info.value.detail)

    def test_잘못된_형식의_시작일_이전_값을_거부한다(self):
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"start_date_to": "06-01-2026"})
        assert "start_date_to" in str(exc_info.value.detail)

    def test_검색어_빈_문자열은_유효한_값으로_받아들인다(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"q": ""})
        # blank strings are accepted as valid (allow_blank=True) but the queryset
        # layer does not filter on them — validated_data will contain the key with ""
        # The querysets.py filter_for_public_listing skips blank values via truthiness check.
        assert result.get("q", "") == ""

    def test_지역_빈_문자열은_유효한_값으로_받아들인다(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"region": ""})
        assert result.get("region", "") == ""

    def test_카테고리_빈_문자열은_유효한_값으로_받아들인다(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"category": ""})
        assert result.get("category", "") == ""

    def test_원작_빈_문자열은_유효한_값으로_받아들인다(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"work_title": ""})
        assert result.get("work_title", "") == ""

    def test_빈_파라미터는_빈_딕셔너리를_반환한다(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({})
        assert result == {}

    def test_DRF_QueryDict이_아닌_일반_딕셔너리도_받아들인다(self):
        """Should accept any Mapping, not just DRF QueryDict."""
        from events.queries import parse_public_listing_params

        raw = {"q": "test"}
        result = parse_public_listing_params(raw)
        assert result["q"] == "test"

    def test_정렬_값을_받아들인다(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"sort": "closing_soon"})
        assert result["sort"] == "closing_soon"

    def test_잘못된_정렬_값은_거부한다(self):
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"sort": "not_a_real_sort"})
        assert "sort" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# list_published_events
# ---------------------------------------------------------------------------

@pytest.mark.domain
@pytest.mark.django_db
class TestListPublishedEvents:
    def test_게시된_행사만_반환한다(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        published = make_event(title="Published")
        make_event(title="Draft", publish_status=Event.PublishStatus.DRAFT)

        qs = list_published_events({}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert published.id in ids
        assert len(ids) == 1

    def test_상태_필터_예정으로_거르면_예정_행사만_반환한다(self, make_event):
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

    def test_상태_필터_진행중으로_거르면_진행중_행사만_반환한다(self, make_event):
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

    def test_기본_정렬은_진행중_예정_종료_순이다(self, make_event):
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

    def test_기준일을_생략해도_결과를_반환한다(self, make_event):
        """When today is omitted, the function still returns a queryset."""
        from events.queries import list_published_events

        make_event(title="Any event")
        qs = list_published_events({})
        assert qs.count() == 1

    def test_마감임박_정렬은_종료되지_않은_행사를_종료일_오름차순으로_먼저_배치하고_날짜_없는_행사는_그_뒤에_둔다(self, make_event):
        """Closing-soon sort ranks not-yet-ended events (end_date null or >= today)
        first, soonest-ending first (nulls last). Already-ended events are pushed
        to the back — see test_마감임박_정렬에서_이미_종료된_행사는_진행중_행사보다_앞에_오지_않는다
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

    def test_마감임박_정렬에서_이미_종료된_행사는_진행중_행사보다_앞에_오지_않는다(self, make_event):
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

    def test_마감임박_정렬의_종료된_그룹_안에서는_최근_종료된_행사가_먼저_온다(self, make_event):
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

    def test_마감임박_정렬에서_종료일이_같으면_id_오름차순으로_정렬한다(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        end_date = today + timedelta(days=5)
        first = make_event(title="First", start_date=today, end_date=end_date)
        second = make_event(title="Second", start_date=today, end_date=end_date)

        qs = list_published_events({"sort": "closing_soon"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids.index(first.id) < ids.index(second.id)

    def test_시작일_오름차순_정렬은_상태와_무관하게_시작일_순으로만_배치한다(self, make_event):
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

    def test_시작일_오름차순_정렬에서_시작일이_같으면_id_오름차순으로_정렬한다(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        start_date = today + timedelta(days=1)
        first = make_event(title="First", start_date=start_date, end_date=today + timedelta(days=10))
        second = make_event(title="Second", start_date=start_date, end_date=today + timedelta(days=10))

        qs = list_published_events({"sort": "start_asc"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids.index(first.id) < ids.index(second.id)

    def test_최신순_정렬은_id_내림차순으로_배치한다(self, make_event):
        from events.queries import list_published_events

        today = date(2026, 6, 24)
        first = make_event(title="First", start_date=today, end_date=today + timedelta(days=5))
        second = make_event(title="Second", start_date=today, end_date=today + timedelta(days=5))

        qs = list_published_events({"sort": "newest"}, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ids == [second.id, first.id]

    def test_정렬_파라미터를_생략하면_기본_정렬을_유지한다(self, make_event):
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

@pytest.mark.unit
class TestPublicListingPageSize:
    def test_공개_목록_페이지_크기는_10건이다(self):
        from events.queries import PUBLIC_LISTING_PAGE_SIZE

        assert PUBLIC_LISTING_PAGE_SIZE == 10


# ---------------------------------------------------------------------------
# with_public_status queryset arms (moved from tests/core/test_coverage_supplements.py)
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
class TestWithPublicStatus:
    def test_종료_상태_필터는_종료된_행사만_포함한다(self, make_event):
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

    def test_상태_필터_active는_종료된_행사만_제외하고_종료일_없는_행사도_포함한다(
        self, make_event
    ):
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
        upcoming = make_event(
            title="예정 행사",
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=12),
        )
        # Off-by-one guard: end_date == today must still count as "not ended
        # yet". Without this fixture, mutating `end_date__lt` to `end_date__lte`
        # in the exclude clause would not be caught by any assertion here.
        ends_today = make_event(
            title="오늘 종료 행사",
            start_date=today - timedelta(days=3),
            end_date=today,
        )
        # Deliberate: end_date=None is the case under test, not a null trap.
        # Part A's "active" predicate treats a missing end date as "not
        # ended", asymmetric with Part B's dataset-carryover predicate.
        no_end_date = make_event(
            title="종료일 없는 행사",
            start_date=today - timedelta(days=30),
            end_date=None,
        )

        result = Event.objects.published().with_public_status("active", today=today)

        assert ended not in result
        assert ongoing in result
        assert upcoming in result
        assert ends_today in result
        assert no_end_date in result

    def test_알_수_없는_상태_필터는_전체_행사를_그대로_반환한다(self, make_event):
        today = date(2026, 7, 1)
        make_event(title="아무 행사")
        qs = Event.objects.published()

        # Unrecognised status falls through every arm to `return self`.
        assert list(qs.with_public_status("nonsense", today=today)) == list(qs)