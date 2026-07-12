"""E2E: mobile viewport horizontal-overflow smoke (375x812 phone width).

Automated re-run of the manual §10 Gate B check ("320px 이상에서 페이지 단위
수평 스크롤 없음") across the pages the mobile-first plan flagged (see the
test cases below for the current route list) — catches a CSS/JS regression
that widens `body.scrollWidth` without waiting for the next manual pass.
"""
import pytest

from archive.models import EventInterest, PersonalEntry, UserEventStatus, VisitRecord

pytestmark = pytest.mark.e2e


@pytest.fixture
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 375, "height": 812}}


def _no_horizontal_overflow(page):
    return page.evaluate("document.body.scrollWidth <= window.innerWidth")


class TestMobileOverflowSmoke:
    def test_home_has_no_horizontal_overflow(self, live_server, page, seed):
        page.goto(live_server.url + "/")

        # The hero carousel applies its "fan" layout (transforms) after init —
        # measuring before that would miss the layout the fan settles into.
        page.wait_for_selector("[data-carousel-track].fan")

        assert _no_horizontal_overflow(page)

    def test_event_list_has_no_horizontal_overflow(self, live_server, page, seed):
        page.goto(f"{live_server.url}/events/")

        assert _no_horizontal_overflow(page)

    def test_event_detail_has_no_horizontal_overflow(self, live_server, page, seed):
        event = seed.events[0]
        page.goto(f"{live_server.url}/events/{event.id}/")

        assert _no_horizontal_overflow(page)

    def test_archive_has_no_horizontal_overflow(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/")

        assert _no_horizontal_overflow(page)

    def test_staff_dashboard_has_no_horizontal_overflow(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_staff@example.com", seed.password)
        page.goto(f"{live_server.url}/staff/dashboard/")

        assert _no_horizontal_overflow(page)

    def test_legal_privacy_has_no_horizontal_overflow(self, live_server, page, seed):
        page.goto(f"{live_server.url}/legal/privacy/")

        assert _no_horizontal_overflow(page)

    def test_legal_terms_has_no_horizontal_overflow(self, live_server, page, seed):
        page.goto(f"{live_server.url}/legal/terms/")

        assert _no_horizontal_overflow(page)

    def test_account_delete_has_no_horizontal_overflow(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/accounts/delete/")

        assert _no_horizontal_overflow(page)

    def test_archive_visits_has_no_horizontal_overflow(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/visits/")

        assert _no_horizontal_overflow(page)

    def test_archive_personal_entries_has_no_horizontal_overflow(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/items/")

        assert _no_horizontal_overflow(page)

    def test_archive_interests_has_no_horizontal_overflow(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/interests/")

        assert _no_horizontal_overflow(page)

    def test_archive_visit_create_has_no_horizontal_overflow(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/visits/new/")

        assert _no_horizontal_overflow(page)


class TestMobileOverflow320px:
    """320px is Chromium's own floor for a native `<input type="file">`
    (~314px min-content) — the 375px class above is too wide to catch a
    track that only breaks at the narrowest supported viewport."""

    @pytest.fixture
    def browser_context_args(self, browser_context_args):
        return {**browser_context_args, "viewport": {"width": 320, "height": 740}}

    def test_archive_personal_entries_has_no_horizontal_overflow(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/items/")

        assert _no_horizontal_overflow(page)

    def test_archive_personal_entries_with_long_unbroken_tokens_has_no_horizontal_overflow(
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

    def test_archive_statuses_interests_visits_with_long_unbroken_subject_has_no_horizontal_overflow(
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
