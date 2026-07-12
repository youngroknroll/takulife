"""E2E regression: status.js's sibling-lock (handleClick, .status-btn
siblings disabled while one is in flight) is not recovered by a bfcache
pageshow restore — api.js's own pageshow listener (see
test_bfcache_loading_reset_e2e.py) only clears .is-loading, which the
sibling lock never sets (it just sets .disabled directly), so a page
restored from bfcache mid-request could show a sibling permanently
disabled with no visual explanation and no way to unlock it short of a full
reload.

Same synthetic-dispatch approach as test_bfcache_loading_reset_e2e.py (see
that file's docstring for why a real back/forward navigation can't be used
as the red/green check in this environment).
"""
import pytest

pytestmark = pytest.mark.e2e


def _dispatch_persisted_pageshow(page):
    page.evaluate(
        "() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))"
    )


class TestStatusSiblingLockBfcacheRecovery:
    def test_sibling_locked_button_resets_but_server_disabled_button_is_untouched(
        self, live_server, page, seed, login
    ):
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/statuses/")

        page.evaluate(
            """() => {
                // Mirrors status.js handleClick's sibling-lock loop: disable
                // a sibling .status-btn and mark it, without touching
                // .is-loading (that belongs to the button actually in flight).
                var container = document.querySelector('[data-status-error-container]');
                var sibling = container.querySelectorAll('.status-btn')[1];
                sibling.disabled = true;
                sibling.classList.add('is-sibling-locked');

                var serverDisabled = document.createElement('button');
                serverDisabled.id = 'server-disabled-probe';
                serverDisabled.disabled = true;
                document.body.appendChild(serverDisabled);
            }"""
        )
        before = page.evaluate(
            """() => {
                var sibling = document.querySelector('[data-status-error-container] .is-sibling-locked');
                return {
                    disabled: sibling.disabled,
                    locked: sibling.classList.contains('is-sibling-locked'),
                    probe: document.getElementById('server-disabled-probe').disabled,
                };
            }"""
        )
        assert before["disabled"] is True
        assert before["locked"] is True
        assert before["probe"] is True

        _dispatch_persisted_pageshow(page)

        after = page.evaluate(
            """() => {
                var sibling = document.querySelectorAll('[data-status-error-container] .status-btn')[1];
                return {
                    disabled: sibling.disabled,
                    locked: sibling.classList.contains('is-sibling-locked'),
                    probe: document.getElementById('server-disabled-probe').disabled,
                };
            }"""
        )
        assert after["disabled"] is False
        assert after["locked"] is False
        # Not marked .is-sibling-locked — a persisted pageshow must leave it alone.
        assert after["probe"] is True
