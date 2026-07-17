"""E2E regression: a button left mid-flight (.is-loading + disabled) before
the user navigates away must not stay frozen forever if the page comes back
from the browser's back/forward cache (bfcache) instead of a fresh network
load — the in-flight request that would have called
window.TakuAPI.setLoading(btn, false) never gets the chance to run again.

Real back/forward navigation does not reliably restore from bfcache in
headless Chromium under Playwright (verified: a real go_back() in this
environment triggers a fresh server reload, wiping the JS-added
.is-loading/disabled state on its own — the exact scenario this fix guards
against never reproduces that way, so it can't be used as a red/green
check). Instead this dispatches a synthetic `pageshow` event with
`persisted: true` — the same signal a genuine bfcache restore fires — to
verify api.js's listener and its .is-loading selector boundary directly.
"""
import pytest

from archive.models import UserEventStatus

pytestmark = pytest.mark.e2e


def _dispatch_persisted_pageshow(page):
    page.evaluate(
        "() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))"
    )


class TestBfcachePageshowResetsLoadingButtons:
    def test_bfcache_복원_시_JS로_로딩중_표시된_버튼은_초기화되고_서버가_비활성화한_버튼은_그대로_유지된다(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        page.evaluate(
            """() => {
                var loadingBtn = document.querySelector('.status-btn');
                window.TakuAPI.setLoading(loadingBtn, true);

                var serverDisabled = document.createElement('button');
                serverDisabled.id = 'server-disabled-probe';
                serverDisabled.disabled = true;
                document.body.appendChild(serverDisabled);
            }"""
        )
        before = page.evaluate(
            """() => ({
                loadingBtn: {
                    disabled: document.querySelector('.status-btn').disabled,
                    loading: document.querySelector('.status-btn').classList.contains('is-loading'),
                },
                probe: document.getElementById('server-disabled-probe').disabled,
            })"""
        )
        assert before["loadingBtn"]["disabled"] is True
        assert before["loadingBtn"]["loading"] is True
        assert before["probe"] is True

        _dispatch_persisted_pageshow(page)

        after = page.evaluate(
            """() => ({
                loadingBtn: {
                    disabled: document.querySelector('.status-btn').disabled,
                    loading: document.querySelector('.status-btn').classList.contains('is-loading'),
                },
                probe: document.getElementById('server-disabled-probe').disabled,
            })"""
        )
        assert after["loadingBtn"]["disabled"] is False
        assert after["loadingBtn"]["loading"] is False
        # Not marked .is-loading — a persisted pageshow must leave it alone.
        assert after["probe"] is True
