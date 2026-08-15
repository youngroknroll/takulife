"""홈 화면 뷰 컨텍스트(web.views.home)를 검증한다.

다루는 범위:
- "카테고리로 둘러보기" 타일: 어휘 순서대로 카테고리마다 타일 1개, 각각
  해당 카테고리의 게시 행사 건수를 담는다.
- 컨텍스트 키 상한(ongoing/closing/recent는 15건 제한).
- D-5 마감임박 창(홈 화면만의 선정 기준).
- 가드: closing_rows의 D+5 행사도 status_slug == "ongoing"이어야 한다.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch

from django.test import Client

from events.models import Event

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestHomeCategoryTiles:
    def test_홈_화면_카테고리_타일은_전체_카테고리를_어휘_순서대로_모두_포함한다(self):
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

    def test_카테고리_타일_건수는_게시된_행사만_집계하고_초안은_제외한다(self, make_event):
        make_event(category="popup_store")
        make_event(category="popup_store")
        make_event(category="exhibition")
        make_event(category="popup_store", publish_status=Event.PublishStatus.DRAFT)

        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["popup_store"]["count"] == 2
        assert tiles["exhibition"]["count"] == 1
        assert tiles["collaboration_cafe"]["count"] == 0

    def test_카테고리_타일은_한글_라벨을_포함한다(self):
        resp = Client().get("/")

        tiles = {t["slug"]: t for t in resp.context["category_tiles"]}
        assert tiles["popup_store"]["label"] == "팝업스토어"
        assert tiles["theater_bonus"]["label"] == "극장 특전"
        assert tiles["fan_meeting"]["label"] == "팬미팅"


@pytest.mark.django_db
class TestHomeContextCaps:
    """홈 화면은 더 많은 항목이 있어도 각 섹션을 15건까지만 노출한다."""

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
                end_date=today + timedelta(days=i % 5 + 1),
            )

    def test_진행중_행사가_15건을_넘으면_홈_화면에_15건까지만_노출된다(self, make_event):
        today = date(2026, 6, 26)
        self._make_ongoing(make_event, today, 16)
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["ongoing_rows"]) == 15

    def test_신규_행사가_15건을_넘으면_홈_화면에_15건까지만_노출된다(self, make_event):
        today = date(2026, 6, 26)
        self._make_recent(make_event, 16)
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["recent_rows"]) == 15

    def test_마감_임박_행사가_15건을_넘으면_홈_화면에_15건까지만_노출된다(self, make_event):
        today = date(2026, 6, 26)
        self._make_closing(make_event, today, 16)
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["closing_rows"]) == 15

    def test_행사가_전혀_없어도_홈_화면_섹션_리스트_키는_빈_리스트로_카테고리_타일_키는_값이_존재한다(self):
        resp = Client().get("/")
        assert resp.context["ongoing_rows"] == []
        assert resp.context["closing_rows"] == []
        assert resp.context["recent_rows"] == []
        assert resp.context["category_tiles"] is not None
        assert resp.context["featured_event_row"] is None


@pytest.mark.django_db
class TestHomeClosingWindow:
    """홈 화면은 D-5 마감임박 창을 쓴다(전역 D-4 창이 아니다)."""

    def test_종료일이_오늘로부터_5일_후인_행사는_마감_임박_목록에_포함된다(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+5 closing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_ids = [row["event"].id for row in resp.context["closing_rows"]]
        assert event.id in closing_ids

    def test_종료일이_오늘로부터_6일_후인_행사는_마감_임박_목록에서_제외된다(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+6 not closing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=6),
        )
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_ids = [row["event"].id for row in resp.context["closing_rows"]]
        assert event.id not in closing_ids


@pytest.mark.django_db
class TestHomeSlidersDropEndedEvents:
    """슬라이더는 기간이 지난 행사(end_date < 오늘)를 숨긴다."""

    def test_종료일이_지난_행사는_신규_행사_목록에서_제외되고_진행중인_행사는_유지된다(self, make_event):
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
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        recent_ids = [row["event"].id for row in resp.context["recent_rows"]]
        assert ended.id not in recent_ids
        assert live.id in recent_ids

    def test_종료일이_없는_행사는_신규_행사_목록에서_계속_유지된다(self, make_event):
        today = date(2026, 6, 26)
        no_dates = make_event(title="No dates")
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        recent_ids = [row["event"].id for row in resp.context["recent_rows"]]
        assert no_dates.id in recent_ids


@pytest.mark.django_db
class TestHomeClosingStatusDivergence:
    """가드: closing_rows에 뽑힌 D+5 행사도 status_slug는 여전히 "ongoing"이다.

    다음 두 기준이 의도적으로 다르다는 것을 기록해 둔다:
    - 홈 선정 기준: ending_within_days(5) — D+5 행사까지 뽑는다.
    - 상태 분류 기준: derive_event_display는 CLOSING_SOON_DAYS==4를 쓰므로
      D+5 행사는 상태상 여전히 "ongoing"이다.

    CLOSING_SOON_DAYS가 5로 바뀌면 이 테스트가 의도치 않은 결합을 잡아낸다.
    """

    def test_마감_임박_목록에_포함된_D플러스5_행사도_상태_슬러그는_진행중이다(self, make_event):
        today = date(2026, 6, 26)
        make_event(
            title="D+5 boundary",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_rows = resp.context["closing_rows"]
        d5_rows = [r for r in closing_rows if r["event"].title == "D+5 boundary"]
        assert len(d5_rows) == 1
        assert d5_rows[0]["status_slug"] == "ongoing"


@pytest.mark.django_db
class TestHomeFeaturedEvent:
    """홈 대표 행사는 조회수 인기 슬라이더가 아니라
    list_published_events 기본 우선순위(진행중 우선 -> 예정 -> 종료, "active"는
    종료 행사를 제외)의 첫 행사 한 건이다."""

    def test_홈_대표_행사는_종료되지_않은_공개_행사_우선순위의_첫_행사다(
        self, make_event, make_draft_event
    ):
        today = date(2026, 6, 26)
        make_event(
            title="종료된 행사",
            start_date=today - timedelta(days=20),
            end_date=today - timedelta(days=1),
        )
        ongoing = make_event(
            title="진행 중 행사",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=3),
        )
        make_event(
            title="예정 행사",
            start_date=today + timedelta(days=10),
        )
        make_draft_event(
            title="조회수 높은 초안",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            view_count=9999,
        )

        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")

        assert resp.context["featured_event_row"]["event"].id == ongoing.id

    def test_공개중인_행사가_없으면_홈_대표_행사는_없다(self):
        resp = Client().get("/")

        assert resp.context["featured_event_row"] is None

    def test_종료된_행사만_있으면_홈_대표_행사는_없다(self, make_event):
        today = date(2026, 6, 26)
        make_event(
            title="종료된 행사 1",
            start_date=today - timedelta(days=20),
            end_date=today - timedelta(days=10),
        )
        make_event(
            title="종료된 행사 2",
            start_date=today - timedelta(days=15),
            end_date=today - timedelta(days=1),
        )

        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")

        assert resp.context["featured_event_row"] is None


@pytest.mark.django_db
class TestHomeCollectionSnapshotContext:
    """컬렉션-퍼스트 홈: 로그인 사용자의 개인화 스냅샷 —
    collection_summary/recent_goods/unrecorded/upcoming_planned/snapshot_active.
    archive.models은 모듈 상단이 아니라 각 테스트 함수 안에서 임포트한다.
    이 클래스만 필요하고, tests/events/에는 archive 팩토리 픽스처가 없기
    때문이다(make_status/make_collection_item은 tests/archive/conftest.py에
    있어 여기서는 범위 밖이다)."""

    SNAPSHOT_KEYS = (
        "collection_summary",
        "recent_goods",
        "unrecorded",
        "upcoming_planned",
        "snapshot_active",
        # 2026-07-23 에디토리얼 리디자인: 통계가 2칸(보유/구함)에서 4칸으로
        # 늘면서 방문 기록 수와 찜 수가 추가됐다. 비로그인 응답에서 새지
        # 않아야 하는 키 목록이므로 여기에도 함께 등재한다.
        "snapshot_visit_count",
        "snapshot_interest_count",
    )

    def test_로그인_사용자의_스냅샷에_방문_기록_수와_찜_수가_담긴다(self, make_user, make_event):
        """4칸 통계의 나머지 두 칸. 보유/구함은 collection_summary가 이미
        담당하고, 이 둘은 각각 VisitRecord와 EventInterest에서 온다."""
        from archive.models import EventInterest, VisitRecord

        user = make_user()
        event = make_event(title="스냅샷카운트행사")
        VisitRecord.objects.create(user=user, event=event, visited_on="2026-07-01")
        EventInterest.objects.create(user=user, event=event)

        client = Client()
        client.force_login(user)
        resp = client.get("/")

        assert resp.status_code == 200
        assert resp.context["snapshot_visit_count"] == 1
        assert resp.context["snapshot_interest_count"] == 1

    def test_기록도_찜도_없는_사용자는_두_카운트가_0이다(self, make_user):
        user = make_user()
        client = Client()
        client.force_login(user)

        resp = client.get("/")

        assert resp.context["snapshot_visit_count"] == 0
        assert resp.context["snapshot_interest_count"] == 0

    def test_비로그인_사용자의_홈_응답에는_컬렉션_스냅샷_컨텍스트_키가_없다(self):
        resp = Client().get("/")

        assert resp.status_code == 200
        for key in self.SNAPSHOT_KEYS:
            assert key not in resp.context

    def test_비로그인_사용자의_홈_응답에는_컬렉션_스냅샷_마크업이_전혀_포함되지_않는다(self):
        """§7-b-1: 템플릿은 위 컨텍스트 키 검사와 별개로 {% if
        request.user.is_authenticated %}로 패널 전체를 한 번 더 막는다 —
        비로그인 응답은 컨텍스트 키만 빠지는 게 아니라 패널 마크업이
        한 바이트도 없어야 한다."""
        resp = Client().get("/")

        assert b"snapshot-panel" not in resp.content
        assert b"hscroll-snap" not in resp.content

    def test_로그인_사용자의_홈_컬렉션_스냅샷은_본인_데이터만_담고_다른_사용자_데이터는_섞이지_않는다(
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

        # 다른 유저도 동일한 3축 데이터를 갖지만, 이 유저의 스냅샷에 섞이면 안 된다.
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
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = client.get("/")

        assert resp.context["collection_summary"] == {
            "owned_count": 1,
            "wanted_count": 0,
            "tradeable_count": 0,
            "total_count": 1,
        }
        assert resp.context["recent_goods"][0].name == "보유 아이템"
        assert resp.context["unrecorded"][0]["subject"]["subject_type"] == "event"
        assert resp.context["unrecorded"][0]["subject"]["subject_id"] == visited_event.id
        assert resp.context["upcoming_planned"][0]["event"].id == upcoming_event.id
        assert "status_slug" in resp.context["upcoming_planned"][0]

    def test_보유_아이템이_5건을_넘으면_스냅샷_최근_굿즈는_5건까지만_노출된다(self, make_user):
        from archive.models import CollectionItem

        user = make_user()
        for i in range(6):
            CollectionItem.objects.create(user=user, name=f"아이템{i}")

        client = Client()
        client.force_login(user)
        resp = client.get("/")

        assert len(resp.context["recent_goods"]) == 5

    def test_기록_미완성_행사가_5건을_넘으면_스냅샷에_5건까지만_노출된다(self, make_user, make_event):
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

    def test_다가오는_방문_예정_행사가_4건을_넘으면_스냅샷에_4건까지만_노출된다(self, make_user, make_event):
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
        with patch("web.views.events.timezone.localdate", return_value=today):
            resp = client.get("/")

        assert len(resp.context["upcoming_planned"]) == 4

    def test_보유는_없고_구하는_아이템만_있어도_컬렉션_스냅샷이_활성화된다(self, make_user):
        """snapshot_active는 보유+구함 기준이다 — 축과 무관하게 등록된 모든
        행을 세는(total_count) 마이페이지의 collection_count와는 일부러
        다르다. 구함만 있는 컬렉션(보유 0)도 스냅샷을 활성화해야 한다."""
        from archive.models import CollectionItem

        user = make_user()
        CollectionItem.objects.create(user=user, name="구하는 아이템", is_wanted=True)

        client = Client()
        client.force_login(user)
        resp = client.get("/")

        assert resp.context["snapshot_active"] is True

    def test_컬렉션_방문_기록이_모두_비어있으면_스냅샷이_비활성화된다(self, make_user):
        user = make_user()

        client = Client()
        client.force_login(user)
        resp = client.get("/")

        assert resp.context["snapshot_active"] is False

    def test_홈_화면을_반복_조회해도_방문_예정_상태_레코드는_생성되거나_변경되지_않는다(
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
        with patch("web.views.events.timezone.localdate", return_value=today):
            client.get("/")
            client.get("/")

        status.refresh_from_db()
        assert UserEventStatus.objects.count() == 1
        assert status.updated_at == original_updated_at
