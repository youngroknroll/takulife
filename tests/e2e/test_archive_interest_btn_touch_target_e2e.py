"""E2E regression: .interest-btn (찜 toggle) meets the §5.4 44px touch
target on /archive/interests/ and /archive/items/ — event_list.css already
scopes this fix to .event-card, but the same global .interest-btn
(controls.css, ~27px pill) renders unscaled in the archive status-card and
직접 등록 visit-card contexts too.
"""
import pytest

from archive.models import EventInterest, PersonalEntry

pytestmark = pytest.mark.e2e


class TestArchiveInterestsInterestBtnTouchTarget:
    def test_찜한_행사_목록의_찜_버튼은_최소_44px_터치_타깃을_만족한다(self, live_server, page, seed, login):
        EventInterest.objects.create(user=seed.user, event=seed.events[0])

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/interests/")

        box = page.locator(".status-card .interest-btn").first.bounding_box()
        assert box["height"] >= 44


class TestPersonalEntriesInterestBtnTouchTarget:
    def test_직접_등록_목록의_찜_버튼은_최소_44px_터치_타깃을_만족한다(self, live_server, page, seed, login):
        # seed already creates one PersonalEntry for e2e_user, but keep this
        # test self-contained instead of depending on that seed detail.
        PersonalEntry.objects.create(
            user=seed.user, kind=PersonalEntry.Kind.PLACE, title="터치 타깃 확인용"
        )

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/items/")

        box = page.locator(".visit-card .interest-btn").first.bounding_box()
        assert box["height"] >= 44
