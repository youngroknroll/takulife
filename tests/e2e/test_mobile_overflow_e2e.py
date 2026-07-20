"""E2E: mobile viewport horizontal-overflow smoke (375x812 phone width).

Automated re-run of the manual §10 Gate B check ("320px 이상에서 페이지 단위
수평 스크롤 없음") across the pages the mobile-first plan flagged (see the
test cases below for the current route list) — catches a CSS/JS regression
that widens `body.scrollWidth` without waiting for the next manual pass.
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from archive.models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
)
from events.models import Event

pytestmark = pytest.mark.e2e


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 375, "height": 812}}


def _no_horizontal_overflow(page):
    return page.evaluate("document.body.scrollWidth <= window.innerWidth")


def _seed_home_snapshot_active_axes(user, today):
    """CollectionItem x2 + an unrecorded-visited event + a future-planned
    event — activates all 3 home snapshot hscroll sublists at once (H-2)."""
    CollectionItem.objects.create(user=user, name="스냅샷 아이템1")
    CollectionItem.objects.create(user=user, name="스냅샷 아이템2")
    unrecorded_event = Event.objects.create(
        title="기록 대기 행사", publish_status=Event.PublishStatus.PUBLISHED
    )
    UserEventStatus.objects.create(
        user=user, event=unrecorded_event, status=UserEventStatus.Status.VISITED
    )
    planned_event = Event.objects.create(
        title="다가오는 스냅샷 행사",
        publish_status=Event.PublishStatus.PUBLISHED,
        start_date=today + timedelta(days=5),
    )
    UserEventStatus.objects.create(
        user=user, event=planned_event, status=UserEventStatus.Status.PLANNED
    )


class TestMobileOverflowSmoke:
    def test_홈_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed):
        page.goto(live_server.url + "/")

        # The hero stack deck signals layout readiness via data-deck-ready
        # after init — measuring before that would miss the settled layout.
        page.wait_for_selector("[data-deck][data-deck-ready]")

        assert _no_horizontal_overflow(page)

    def test_행사_목록_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed):
        page.goto(f"{live_server.url}/events/")

        assert _no_horizontal_overflow(page)

    def test_행사_상세_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed):
        event = seed.events[0]
        page.goto(f"{live_server.url}/events/{event.id}/")

        assert _no_horizontal_overflow(page)

    def test_아카이브_전체_보기_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/")

        assert _no_horizontal_overflow(page)

    def test_스태프_대시보드_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/dashboard/")

        assert _no_horizontal_overflow(page)

    def test_개인정보처리방침_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed):
        page.goto(f"{live_server.url}/legal/privacy/")

        assert _no_horizontal_overflow(page)

    def test_이용약관_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed):
        page.goto(f"{live_server.url}/legal/terms/")

        assert _no_horizontal_overflow(page)

    def test_회원_탈퇴_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/accounts/delete/")

        assert _no_horizontal_overflow(page)

    def test_다녀온_기록_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/visits/")

        assert _no_horizontal_overflow(page)

    def test_직접_등록_화면은_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/items/")

        assert _no_horizontal_overflow(page)

    def test_찜_목록_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/interests/")

        assert _no_horizontal_overflow(page)

    def test_다녀온_기록_작성_화면은_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/visits/new/")

        assert _no_horizontal_overflow(page)

    def test_내_컬렉션_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/")

        assert _no_horizontal_overflow(page)

    def test_컬렉션_항목_등록_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/new/")

        assert _no_horizontal_overflow(page)

    def test_컬렉션_항목_수정_화면은_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        item = CollectionItem.objects.create(user=seed.user, name="아이템")

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/{item.id}/edit/")

        assert _no_horizontal_overflow(page)

    def test_홈_컬렉션_스냅샷_기본_상태_화면은_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/")

        assert _no_horizontal_overflow(page)

    def test_홈_컬렉션_스냅샷_3개_영역이_모두_활성화된_화면은_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        today = date(2026, 6, 26)
        _seed_home_snapshot_active_axes(seed.user, today)

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        with patch("core.views.timezone.localdate", return_value=today):
            page.goto(f"{live_server.url}/")

        assert _no_horizontal_overflow(page)


class TestMobileOverflow320px:
    """320px is Chromium's own floor for a native `<input type="file">`
    (~314px min-content) — the 375px class above is too wide to catch a
    track that only breaks at the narrowest supported viewport."""

    @pytest.fixture
    def browser_context_args(self, browser_context_args):
        return {**browser_context_args, "viewport": {"width": 320, "height": 740}}

    def test_직접_등록_화면은_320px에서_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/items/")

        assert _no_horizontal_overflow(page)

    def test_긴_끊어지지_않는_메모와_카테고리를_가진_직접_등록_항목_화면은_320px에서_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        """memo/category are free-text fields with no whitespace requirement —
        a long unbroken token (URL, run-on category label) must wrap instead
        of pushing the card wider than the viewport."""
        PersonalEntry.objects.create(
            user=seed.user,
            kind=PersonalEntry.Kind.PLACE,
            title="긴 토큰 테스트",
            category="a" * 30,
            memo="https://example.com/" + "a" * 40,
        )

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/items/")

        assert _no_horizontal_overflow(page)

    def test_긴_끊어지지_않는_제목의_직접_등록_주체는_나의_일정_찜_다녀온_기록_화면에서_320px_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        """A 직접 등록 subject with a long, unbroken title (URL) and category
        (free-input classification) — rendered as an <h3> (line-clamped but
        not word-broken by default) and an .event-category chip
        (white-space: nowrap by default) — pushed all three cards that
        reference the subject wider than the viewport."""
        entry = PersonalEntry.objects.create(
            user=seed.user,
            kind=PersonalEntry.Kind.PLACE,
            title="https://example.com/" + "a" * 60,
            category="b" * 40,
            location_name="긴 분류명 오버플로우 재현용 장소",
        )
        UserEventStatus.objects.create(
            user=seed.user, personal_entry=entry, status=UserEventStatus.Status.PLANNED
        )
        EventInterest.objects.create(user=seed.user, personal_entry=entry)
        VisitRecord.objects.create(
            user=seed.user,
            personal_entry=entry,
            visited_on="2026-06-15",
            short_review="긴 URL 재현 확인용 방문 기록",
        )

        login(page, live_server.url, "e2e_user@example.com", seed.password)

        page.goto(f"{live_server.url}/archive/statuses/")
        assert _no_horizontal_overflow(page)

        page.goto(f"{live_server.url}/archive/interests/")
        assert _no_horizontal_overflow(page)

        page.goto(f"{live_server.url}/archive/visits/")
        assert _no_horizontal_overflow(page)

    def test_내_컬렉션_화면은_320px에서_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/")

        assert _no_horizontal_overflow(page)

    def test_컬렉션_항목_등록_화면은_320px에서_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/new/")

        assert _no_horizontal_overflow(page)

    def test_컬렉션_항목_수정_화면은_320px에서_가로_스크롤_오버플로우가_없다(self, live_server, page, seed, login):
        item = CollectionItem.objects.create(user=seed.user, name="아이템")

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/{item.id}/edit/")

        assert _no_horizontal_overflow(page)

    def test_홈_컬렉션_스냅샷_기본_상태_화면은_320px에서_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/")

        assert _no_horizontal_overflow(page)

    def test_홈_컬렉션_스냅샷_3개_영역이_모두_활성화된_화면은_320px에서_가로_스크롤_오버플로우가_없다(
        self, live_server, page, seed, login
    ):
        today = date(2026, 6, 26)
        _seed_home_snapshot_active_axes(seed.user, today)

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        with patch("core.views.timezone.localdate", return_value=today):
            page.goto(f"{live_server.url}/")

        assert _no_horizontal_overflow(page)
