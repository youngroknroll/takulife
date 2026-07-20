"""E2E: archive debounced live search (the JS layer unit tests can't cover).

Drives real Chromium: typing swaps only #archive-results, the URL stays in
sync, back/forward restores, and a status button on a *swapped-in* card still
fires its write (proving the archive:listswapped rebinding works end to end).
"""
import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

SEARCH = '.archive-search input[name="q"]'
CARDS = "#archive-results .status-card"


class TestArchiveLiveSearch:
    def test_검색어를_입력하면_목록이_실시간으로_필터링되고_URL에_동기화된다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        # All four planned statuses are present initially.
        expect(page.locator(CARDS)).to_have_count(4)

        page.fill(SEARCH, "여름")

        # Debounced fetch swaps the fragment down to the single match…
        expect(page.locator(CARDS)).to_have_count(1)
        expect(page.locator(CARDS).first).to_contain_text("여름 팝업스토어")
        # …and the URL reflects the term (pushState), without partial=1.
        expect(page).to_have_url(re.compile(r"\?q=%EC%97%AC%EB%A6%84"))
        assert "partial" not in page.url

    def test_검색어를_지우면_전체_목록이_복원된다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        page.fill(SEARCH, "여름")
        expect(page.locator(CARDS)).to_have_count(1)

        # Emptying the box (debounced) brings every card back.
        page.fill(SEARCH, "")
        expect(page.locator(CARDS)).to_have_count(4)
        expect(page).to_have_url(re.compile(r"/archive/statuses/$"))

    def test_뒤로가기를_누르면_이전_검색_결과가_복원된다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        page.fill(SEARCH, "여름")
        expect(page.locator(CARDS)).to_have_count(1)

        page.go_back()

        # popstate replays the empty query: input cleared, full list restored.
        expect(page.locator(CARDS)).to_have_count(4)
        expect(page.locator(SEARCH)).to_have_value("")

    def test_검색_결과가_없으면_빈_상태_문구를_보여준다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        page.fill(SEARCH, "존재하지않는검색어zzz")

        expect(page.locator(CARDS)).to_have_count(0)
        expect(page.locator("#archive-results .empty-state")).to_contain_text(
            "검색 결과가 없습니다"
        )

    def test_실시간_검색으로_교체된_카드의_상태_버튼을_클릭해도_변경이_저장된다(
        self, live_server, page, seed, login
    ):
        """The strongest rebinding proof: act on a card that only exists after a
        live-search swap, and confirm the write reaches the server."""
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        # Isolate the planned "가을 극장 특전" card via live search.
        page.fill(SEARCH, "가을")
        expect(page.locator(CARDS)).to_have_count(1)
        card = page.locator(CARDS).first
        expect(card.locator(".user-status")).to_contain_text("방문 예정")

        # Click 놓침 on the swapped-in card → status.js PATCHes then reloads.
        card.locator('button.status-btn.missed[data-status-action="change"]').click()

        # After the reload the same (still q=가을) page renders the new status.
        expect(page.locator(f"{CARDS} .user-status")).to_contain_text("놓침")

        # And it is durable in the DB, not just the DOM.
        from archive.models import UserEventStatus

        status = UserEventStatus.objects.get(
            user=seed.user, event=seed.events[3]
        )
        assert status.status == "missed"

    def test_검색어를_입력하면_결과_요약_리전에_건수가_표시된다(self, live_server, page, seed, login):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        page.fill(SEARCH, "여름")

        # Debounced swap narrows the list to the single planned match…
        expect(page.locator(CARDS)).to_have_count(1)
        # …and the SSR status region reports the same server-truth count.
        expect(page.locator("#archive-search-status")).to_have_text("1건 검색됨")
