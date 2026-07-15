"""E2E regression: the PATCH-404 form lock (collection.js's lockForm, applied
when a concurrently-deleted item makes the edit form's submit target gone)
must survive a bfcache restore.

Root cause this guards against: bindEditForm's submit handler called
window.TakuAPI.setLoading(submitBtn, true) before the PATCH, which sets both
button.disabled and the .is-loading class. If the 404 branch returned before
the sibling handlers' usual window.TakuAPI.setLoading(submitBtn, false) call,
submitBtn kept .is-loading even after lockForm() additionally set
disabled = true directly on every control. api.js's global pageshow listener
(api.js:380-387) is unconditional and scoped only to .is-loading — on a
bfcache restore it would re-enable *just* submitBtn, leaving it clickable
while every other field lockForm touched stayed correctly disabled. This is
directly reachable: the 404 branch's own revealBackLink() offers a "목록으로
돌아가기" link, and clicking it then pressing the browser Back button is a
completely ordinary bfcache-restore path — not a hypothetical.

Same synthetic-dispatch approach as test_bfcache_loading_reset_e2e.py (see
that file's docstring for why a real back/forward navigation can't be used
as the red/green check in this environment).
"""
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

SUBMIT = '#collection-edit-form button[type="submit"]'


def _dispatch_persisted_pageshow(page):
    page.evaluate(
        "() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))"
    )


class TestCollectionEditBfcacheLockDurability:
    def test_submit_button_stays_disabled_after_bfcache_restore(
        self, live_server, page, seed, login
    ):
        from archive.models import CollectionItem

        item = CollectionItem.objects.create(user=seed.user, name="bfcache 잠금 테스트")

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/collection/{item.id}/edit/")

        # Concurrent delete: the row is gone before this page's own submit
        # reaches the server, reproducing the deterministic 404 race.
        item.delete()

        page.fill("#collection-name", "수정 시도")
        page.click(SUBMIT)

        submit_btn = page.locator(SUBMIT)
        # Wait for the 404 branch to actually settle (not just the
        # synchronous pre-await disable from setLoading(true), which is
        # indistinguishable from the locked state by `disabled` alone) —
        # the back-link only appears once lockForm()/revealBackLink() ran.
        expect(page.locator("#collection-back-link")).to_be_visible()
        expect(submit_btn).to_be_disabled()
        # The lock must already have cleared .is-loading by this point —
        # not just at the moment lockForm's disabled=true was applied.
        assert not submit_btn.evaluate("el => el.classList.contains('is-loading')")

        _dispatch_persisted_pageshow(page)

        expect(submit_btn).to_be_disabled()
        assert not submit_btn.evaluate("el => el.classList.contains('is-loading')")
