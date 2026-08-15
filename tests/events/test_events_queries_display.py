"""events/queries.py와 events/presenters.py를 검증한다: 표시값 도출,
조회수순/마감임박 쿼리셋, 스태프 목록.

다루는 범위:
- derive_event_display: 상태 분류, closing_soon 경계, dday, null 날짜
- most_viewed / ending_within_days: EventQuerySet 정렬·필터 메서드
- list_staff_events: 스태프 품질경고 드릴다운 목록
"""
import pytest
from datetime import date, timedelta

from events.models import Event


@pytest.mark.unit
class TestDeriveEventDisplay:
    def test_시작_예정일_전이면_상태는_예정이고_디데이는_시작까지_남은_일수다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today + timedelta(days=3), end_date=today + timedelta(days=10))
        result = derive_event_display(event, today=today)

        assert result["status"] == "upcoming"
        assert result["dday"] == 3

    def test_진행_기간_중이면_상태는_진행중이고_디데이는_종료까지_남은_일수다(self):
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=2), end_date=today + timedelta(days=5))
        result = derive_event_display(event, today=today)

        assert result["status"] == "ongoing"
        assert result["dday"] == 5

    def test_종료일이_4일_후면_마감임박_상태로_분류된다(self):
        """종료일이 오늘+4일인 경계값이 closing_soon 창 안에 정확히 포함된다."""
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=1), end_date=today + timedelta(days=4))
        result = derive_event_display(event, today=today)

        assert result["status"] == "closing_soon"
        assert result["dday"] == 4

    def test_종료일이_오늘이면_마감임박_상태로_분류된다(self):
        """종료일이 오늘이어도 closing_soon이다(오늘 종료)."""
        from events.presenters import derive_event_display

        today = date(2026, 6, 24)
        event = Event(start_date=today - timedelta(days=2), end_date=today)
        result = derive_event_display(event, today=today)

        assert result["status"] == "closing_soon"
        assert result["dday"] == 0

    def test_종료일이_5일_후면_마감임박이_아닌_진행중_상태로_분류된다(self):
        """종료일이 오늘+5일이면 closing_soon이 아니라 ongoing이다."""
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
        """today를 넘기지 않아도 결과 딕셔너리를 반환한다."""
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

        result = list(Event.objects.published().most_viewed(5))
        ids = [e.id for e in result]
        assert ids.index(second.id) < ids.index(first.id)


@pytest.mark.domain
@pytest.mark.django_db
class TestEndingWithinDays:
    """EventQuerySet.ending_within_days(days, today=today)의 동작을 검증한다.

    선정 규칙: 게시·진행중이며 end_date가 오늘(포함)부터 오늘+days(포함)
    사이인 행사를, 종료가 빠른 순으로 정렬해 반환한다.
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
        """start_date가 오늘보다 미래면 아직 시작 전이라 제외돼야 한다."""
        today = date(2026, 6, 26)
        event = make_event(
            title="Not started yet",
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        qs = Event.objects.published().ending_within_days(5, today=today)
        assert event.id not in list(qs.values_list("id", flat=True))

    def test_초안_행사는_종료일이_창_안에_있어도_제외된다(self, make_event):
        """초안 행사는 end_date가 창 안에 있어도 나타나면 안 된다."""
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


# 경고 드릴다운은 대응하는 count_published_* 함수가 세는 것과 정확히 같은
# 대상 집합을 반환해야 한다(대시보드 드릴다운 정합성). 알 수 없거나 빈 경고
# 값은 무시된다(경고 필터 없음으로 폴백) — 스태프 화면의 기존
# selected_status 정규화 패턴과 같은 방식이다.


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

    def test_폐기된_포스터_경고는_행사_목록을_좁히지_않는다(
        self, make_event, make_draft_event
    ):
        # 포스터 필드와 경고가 서비스 전체에서 폐기됐으므로, "missing_poster"는
        # 더 이상 알려진 경고 키가 아니다. 알 수 없는 경고 키를 넘기면
        # list_staff_events가 필터 없이 게시·초안 행사를 모두 반환하는
        # 기존 계약(알_수_없는_경고_필터_테스트와 동일한 형태)을 그대로 따른다.
        from events.queries import list_staff_events

        published = make_event(official_url="https://example.com/a")
        draft = make_draft_event(official_url="https://example.com/b")

        result = list_staff_events(warning="missing_poster")

        ids = {e.id for e in result}
        assert ids == {published.id, draft.id}

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

    def test_재확인_대상_경고_필터는_기준일_인자_기준으로_해당_행사만_포함한다(
        self, make_event
    ):
        from events.queries import list_staff_events

        today = date(2020, 6, 15)
        # 해당됨: start_date가 오늘이라 D-7 창(start_date - 7일 <= 오늘) 안이고,
        # end_date가 미래라 아직 종료되지 않았으며, verified_at이 NULL이라 미확인.
        needs_reverification = make_event(
            official_url="https://example.com/needs-reverification",
            start_date=today,
            end_date=today + timedelta(days=30),
        )
        # 해당 안 됨: start_date를 먼 미래(오늘+30일)로 잡아 D-7 창 밖으로
        # 벗어나게 한다(reverify_deadline = start_date - 7일 > 오늘).
        # verified_at은 여기서도 NULL로 두어, "미확인" 여부가 아니라 창 밖이라는
        # 이유 하나만으로 제외됨을 분명히 한다.
        outside_window = make_event(
            official_url="https://example.com/outside-window",
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=60),
        )

        result = list_staff_events(warning="needs_reverification", today=today)

        ids = {e.id for e in result}
        assert needs_reverification.id in ids
        assert outside_window.id not in ids

    def test_경고_조건에_맞아도_초안_행사는_경고_필터_결과에서_제외된다(
        self, make_draft_event
    ):
        """경고 드릴다운은 count_published_*와 마찬가지로 게시된 행사만 대상으로 한다."""
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
        """드릴다운 결과 건수는 대시보드의 count_published_* 값과 같아야 한다."""
        from events.queries import count_published_missing_region, list_staff_events

        make_event(official_url="https://example.com/a", region="")
        make_event(official_url="https://example.com/b", region="")
        make_draft_event(official_url="https://example.com/c", region="")

        result = list_staff_events(warning="missing_region")

        assert result.count() == count_published_missing_region()


@pytest.mark.domain
@pytest.mark.django_db
class TestRelatedTo:
    """EventQuerySet.related_to(event, *, today, limit=3)의 동작을 검증한다.

    선정 규칙: 대상 행사와 같은 카테고리를 가진 게시 행사를(자기 자신 제외)
    기존 공개 목록의 상태 정렬 기준으로 정렬해 limit 개까지 반환한다.
    카테고리가 빈 행사는 관련 행사가 없다(빈 쿼리셋).
    """

    def test_같은_카테고리의_다른_공개_행사를_관련_행사로_반환한다(self, make_event):
        today = date(2026, 6, 26)
        base = make_event(title="Base", category="popup_store")
        other = make_event(title="Other", category="popup_store")

        result = Event.objects.published().related_to(base, today=today)

        assert other.id in list(result.values_list("id", flat=True))

    def test_다른_카테고리_행사는_관련_행사에서_제외된다(self, make_event):
        today = date(2026, 6, 26)
        base = make_event(title="Base", category="popup_store")
        other = make_event(title="Other", category="exhibition")

        result = Event.objects.published().related_to(base, today=today)

        assert other.id not in list(result.values_list("id", flat=True))

    def test_자기_자신은_관련_행사에서_제외된다(self, make_event):
        today = date(2026, 6, 26)
        base = make_event(title="Base", category="popup_store")

        result = Event.objects.published().related_to(base, today=today)

        assert base.id not in list(result.values_list("id", flat=True))

    def test_limit_개수를_넘는_관련_행사는_반환하지_않는다(self, make_event):
        today = date(2026, 6, 26)
        base = make_event(title="Base", category="popup_store")
        for i in range(5):
            make_event(title=f"Other {i}", category="popup_store")

        result = list(Event.objects.published().related_to(base, today=today, limit=3))

        assert len(result) <= 3

    def test_카테고리가_빈_행사는_관련_행사가_없다(self, make_event):
        """카테고리가 빈 행사는 '같은 카테고리'라는 관계 자체가 성립하지 않는다."""
        today = date(2026, 6, 26)
        base = make_event(title="Base", category="")
        make_event(title="Other", category="")

        result = Event.objects.published().related_to(base, today=today)

        assert list(result) == []

    def test_published_체인_뒤에서_초안_행사는_관련_행사에서_제외된다(self, make_event):
        today = date(2026, 6, 26)
        base = make_event(title="Base", category="popup_store")
        draft = make_event(
            title="Draft",
            category="popup_store",
            publish_status=Event.PublishStatus.DRAFT,
        )

        result = Event.objects.published().related_to(base, today=today)

        assert draft.id not in list(result.values_list("id", flat=True))
