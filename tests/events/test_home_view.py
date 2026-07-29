"""Tests for the home page view context (core.views.home).

Covers:
- "카테고리로 둘러보기" tiles: one tile per vocab category, in vocab order,
  each carrying the count of *published* events in that category.
- Context key caps (ongoing/closing/recent limited to 15).
- D-5 closing window (home-only selection concern).
- Guard: D+5 events in closing_rows still have status_slug == "ongoing".
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
        # a draft in popup_store must NOT be counted
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
    """Home view limits each section to 15 items even when more exist."""

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
                end_date=today + timedelta(days=i % 5 + 1),  # D+1 to D+5
            )

    def test_진행중_행사가_15건을_넘으면_홈_화면에_15건까지만_노출된다(self, make_event):
        today = date(2026, 6, 26)
        self._make_ongoing(make_event, today, 16)
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["ongoing_rows"]) == 15

    def test_신규_행사가_15건을_넘으면_홈_화면에_15건까지만_노출된다(self, make_event):
        today = date(2026, 6, 26)
        self._make_recent(make_event, 16)
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["recent_rows"]) == 15

    def test_마감_임박_행사가_15건을_넘으면_홈_화면에_15건까지만_노출된다(self, make_event):
        today = date(2026, 6, 26)
        self._make_closing(make_event, today, 16)
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        assert len(resp.context["closing_rows"]) == 15

    def test_행사가_전혀_없어도_홈_화면_섹션_리스트_키는_빈_리스트로_카테고리_타일_키는_값이_존재한다(self):
        resp = Client().get("/")
        assert resp.context["ongoing_rows"] == []
        assert resp.context["closing_rows"] == []
        assert resp.context["recent_rows"] == []
        assert resp.context["category_tiles"] is not None
        assert resp.context["popular_rows"] == []


@pytest.mark.django_db
class TestHomeClosingWindow:
    """Home view uses a D-5 closing window (not the global D-4 window)."""

    def test_종료일이_오늘로부터_5일_후인_행사는_마감_임박_목록에_포함된다(self, make_event):
        today = date(2026, 6, 26)
        event = make_event(
            title="D+5 closing",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        with patch("core.views.events.timezone.localdate", return_value=today):
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
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_ids = [row["event"].id for row in resp.context["closing_rows"]]
        assert event.id not in closing_ids


@pytest.mark.django_db
class TestHomeSlidersDropEndedEvents:
    """Sliders hide events whose period has passed (end_date < today)."""

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
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        recent_ids = [row["event"].id for row in resp.context["recent_rows"]]
        assert ended.id not in recent_ids
        assert live.id in recent_ids

    def test_종료일이_없는_행사는_신규_행사_목록에서_계속_유지된다(self, make_event):
        today = date(2026, 6, 26)
        no_dates = make_event(title="No dates")
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        recent_ids = [row["event"].id for row in resp.context["recent_rows"]]
        assert no_dates.id in recent_ids


@pytest.mark.django_db
class TestHomePosterSectionsAlwaysRenderSlider:
    """The 3 poster sections (이번 주/곧 종료/새 이벤트) used to branch on row
    count — a section at or below its threshold (ongoing<=6, closing<=3,
    recent<=6) rendered a static .poster-card-grid instead of the
    hscroll-wrap slider the other sections used, producing a visibly
    different layout (no arrows, left-aligned static grid) whenever a
    section happened to have few rows. All 3 sections now always render the
    hscroll-wrap markup regardless of row count; hscroll.js hides the arrows
    via visibility when there's nothing to scroll."""

    def test_마감_임박_섹션은_행이_적어도_정적_그리드_대신_hscroll_슬라이더로_렌더링된다(self, make_event):
        today = date(2026, 6, 26)
        for i in range(3):
            make_event(
                title=f"Closing {i}",
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=i % 5 + 1),
            )
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")

        assert len(resp.context["closing_rows"]) == 3
        body = resp.content.decode()
        assert 'id="hscroll-closing"' in body
        assert "poster-card-grid" not in body


@pytest.mark.django_db
class TestHomeClosingStatusDivergence:
    """Guard: a D+5 event selected into closing_rows is still status_slug=="ongoing".

    This documents the intentional divergence between:
    - Home selection: ending_within_days(5) — selects D+5 events.
    - Status classification: derive_event_display uses CLOSING_SOON_DAYS==4, so
      a D+5 event is still "ongoing" from a status perspective.

    If CLOSING_SOON_DAYS is ever changed to 5, this test will catch the
    accidental coupling.
    """

    def test_마감_임박_목록에_포함된_D플러스5_행사도_상태_슬러그는_진행중이다(self, make_event):
        today = date(2026, 6, 26)
        make_event(
            title="D+5 boundary",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
        )
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = Client().get("/")
        closing_rows = resp.context["closing_rows"]
        d5_rows = [r for r in closing_rows if r["event"].title == "D+5 boundary"]
        assert len(d5_rows) == 1
        assert d5_rows[0]["status_slug"] == "ongoing"


@pytest.mark.django_db
class TestHomeCollectionSnapshotContext:
    """Collection-first home (H-1 행위 C): a logged-in user's personalized
    snapshot — collection_summary/recent_goods/unrecorded/upcoming_planned/
    snapshot_active. archive.models is imported inside each test function
    (not at module top) since only this class needs it and tests/events/
    carries no archive factory fixtures (make_status/make_collection_item
    live in tests/archive/conftest.py, out of scope here)."""

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
        """§7-b-1: the template gates the whole panel behind {% if
        request.user.is_authenticated %} as a second, template-level
        defence beyond the context-key check above — an anonymous response
        must carry zero bytes of the panel's markup, not just miss its
        context keys."""
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

        # other user seeded identically on all 3 axes — must never leak into
        # this user's snapshot.
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
        with patch("core.views.events.timezone.localdate", return_value=today):
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
        with patch("core.views.events.timezone.localdate", return_value=today):
            resp = client.get("/")

        assert len(resp.context["upcoming_planned"]) == 4

    def test_보유는_없고_구하는_아이템만_있어도_컬렉션_스냅샷이_활성화된다(self, make_user):
        """snapshot_active is owned+wanted (H4) — deliberately different from
        mypage's collection_count, which counts every registered row
        (total_count) regardless of axis membership. A wanted-only
        collection (owned 0) must still activate the snapshot."""
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
        with patch("core.views.events.timezone.localdate", return_value=today):
            client.get("/")
            client.get("/")

        status.refresh_from_db()
        assert UserEventStatus.objects.count() == 1
        assert status.updated_at == original_updated_at
