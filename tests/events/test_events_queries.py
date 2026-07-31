"""events/queries.py를 검증한다: 목록 파라미터, 게시 행사 목록.

다루는 범위:
- parse_public_listing_params: 필터링, 검증, 빈 문자열 처리
- list_published_events: 고정 today 기준 정렬과 상태 필터링
- PUBLIC_LISTING_PAGE_SIZE: 페이지 크기 상수
"""
import pytest
from datetime import date, timedelta

from events.models import Event


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
        # region/category는 다중값 필드라 단일 값도 원소 1개짜리 리스트로 정규화된다.
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

    def test_상태값_all은_유효한_값으로_받아들여진다(self):
        from events.queries import parse_public_listing_params

        result = parse_public_listing_params({"status": "all"})
        assert result["status"] == "all"

    def test_뷰_전용_active_상태값도_잘못된_값으로_거부한다(self):
        """"active"는 공개 API 계약이 아니다.

        "active"는 `core/views.py::event_list`가 파싱 이후 주입하는
        뷰 내부 전용 값이다. `events/querysets.py::with_public_status`의
        "active" 분기에는 이미 "View-internal only" 주석이 달려 있다.

        이 테스트가 잠그는 것: 누군가 `EventQuerySerializer.STATUS_CHOICES`에
        "active"를 추가하면 이 테스트가 깨진다 — 공개 목록 API가 뷰 전용 값을
        그대로 받아들이게 되는 계약 확장을 여기서 막는다.
        """
        from events.queries import parse_public_listing_params
        from rest_framework.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            parse_public_listing_params({"status": "active"})
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
        # 빈 문자열은 유효한 값으로 받아들여지지만(allow_blank=True) 쿼리셋 계층에서는
        # 걸러지지 않는다 — events/querysets.py의 filter_for_public_listing이
        # truthiness 검사로 빈 값을 건너뛴다.
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
        """QueryDict뿐 아니라 임의의 Mapping도 받아들여야 한다."""
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
        """today를 생략해도 쿼리셋을 반환한다."""
        from events.queries import list_published_events

        make_event(title="Any event")
        qs = list_published_events({})
        assert qs.count() == 1

    def test_마감임박_정렬은_종료되지_않은_행사를_종료일_오름차순으로_먼저_배치하고_날짜_없는_행사는_그_뒤에_둔다(self, make_event):
        """마감임박 정렬은 아직 종료되지 않은 행사(end_date가 null이거나 오늘 이후)를
        종료 빠른 순으로 먼저 두고 null은 맨 뒤에 둔다. 이미 종료된 행사는 그
        뒤로 밀린다 — 이 회귀를 막는 테스트는
        test_마감임박_정렬에서_이미_종료된_행사는_진행중_행사보다_앞에_오지_않는다다."""
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
        """회귀 가드: 오래전 종료된 행사(end_date가 가장 작음)가 closing_soon
        정렬에서 현재 진행중인 행사보다 앞서면 안 된다."""
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
        """이미 종료된 그룹 안에서는 가장 최근에 종료된 행사가 먼저 온다."""
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
        """start_asc 정렬은 기본 진행중/예정/종료 상태 순위를 무시하고 순수하게
        start_date로만 정렬해야 한다(여기서 종료 행사가 가장 이른 start_date를
        가지지만 기본 order_for_public_listing에서는 맨 뒤로 밀린다)."""
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
        """회귀 가드: sort를 생략해도 기존 기본 정렬이 바뀌면 안 된다."""
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

    def test_상태값_all은_종료된_행사도_포함한다(self, make_event):
        """status="all"은 필터 없음과 같이 동작한다 — 종료 행사도 포함된다.

        다른 테스트들의 관례(raw dict를 바로 list_published_events에 넘기는 것)와
        달리 일부러 parse_public_listing_params를 거친다. with_public_status는
        "all" 전용 분기가 없어 인식 못한 문자열은 무필터와 동일하게
        `return self`로 빠지므로, raw dict를 바로 넘기면 serializer가 "all"을
        유효한 값으로 받아들이든 아니든 통과해버려 검증 의미가 없어진다. 이
        테스트의 목적은 "all"이 API가 쓰는
        EventQuerySerializer.STATUS_CHOICES 검증 계층을 실제로 통과하는지
        확인하는 것이다.
        """
        from events.queries import list_published_events, parse_public_listing_params

        today = date(2026, 6, 24)
        ended = make_event(
            title="Ended",
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=1),
        )
        ongoing = make_event(
            title="Ongoing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )

        params = parse_public_listing_params({"status": "all"})
        qs = list_published_events(params, today=today)
        ids = list(qs.values_list("id", flat=True))
        assert ended.id in ids
        assert ongoing.id in ids


@pytest.mark.unit
class TestPublicListingPageSize:
    def test_공개_목록_페이지_크기는_10건이다(self):
        from events.queries import PUBLIC_LISTING_PAGE_SIZE

        assert PUBLIC_LISTING_PAGE_SIZE == 10


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
        # 경계값 가드: end_date == today는 여전히 "아직 종료 안 됨"으로 쳐야 한다.
        # 이 픽스처가 없으면 exclude절의 end_date__lt를 end_date__lte로
        # 되돌리는 뮤테이션을 어떤 단언도 잡지 못한다.
        ends_today = make_event(
            title="오늘 종료 행사",
            start_date=today - timedelta(days=3),
            end_date=today,
        )
        # 의도적: end_date=None이 이 테스트가 검증하는 케이스다(널 함정이 아니다).
        # "active" 판정은 종료일 없음을 "아직 종료 안 됨"으로 취급하며, 이는
        # 다른 판정 로직과 비대칭이다.
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

        # 인식하지 못하는 상태값은 모든 분기를 거쳐 `return self`로 빠진다.
        assert list(qs.with_public_status("nonsense", today=today)) == list(qs)