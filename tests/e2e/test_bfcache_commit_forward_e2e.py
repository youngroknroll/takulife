"""E2E regression: the bfcache-duplicate-creation fix's commit-and-forward
contract (INTG-FE-01/02/03, `.docs/plans/2026-07-18-bfcache-duplicate-
creation-plan.md` §4-2/§5-2/§7/§9).

Root cause this guards against: a submit whose POST already succeeded (201)
navigates away via `window.location.assign`. If the browser restores that
page from bfcache instead of doing a fresh load, the submit button can come
back mid-"in-flight" (`.is-loading` + disabled) with no further JS ever
running to finish the job — a naive "reset every `.is-loading` button on
`pageshow`" fix (the one `test_bfcache_loading_reset_e2e.py` guards) would
re-arm an already-committed submit button and let the user fire a duplicate
POST. `TakuAPI.commitAndNavigate` (api.js) marks the button with
`data-committed-redirect=<url>` right before the `assign` that leaves the
page; the global `pageshow` listener reads that marker on restore and
forces the page on with `location.replace` instead of re-arming the button
— one hop collapses the restored snapshot instead of leaving a
Back→form→forced-forward→Back→form loop.

§7 reproduction technique (BIR design, mirrors the 3 existing bfcache e2e
files in this directory) — **revised from the original plan** after
empirical failure: `Object.defineProperty(window.location, 'assign', ...)`
throws `TypeError: Cannot redefine property: assign` in Chromium — `Location`
is an unforgeable platform object, so `window.location.assign`/`.replace`
cannot be stubbed at all, by any means, from page script. The technique
actually used:
  1. `page.route` aborts the *document* request for the forced-forward
     destination (e.g. `**/collection/`) — an aborted top-level navigation
     leaves the current document alive instead of tearing it down, so the
     marker/disabled state this test inspects afterward survives, while the
     abort still gets recorded as proof a navigation to that URL was
     attempted (real `assign()`/`replace()` calls, unmodified). The abort's
     error code must be `"aborted"` (ERR_ABORTED, cancellation semantics) —
     the default `"failed"` code replaces the main-frame document with a
     chrome-error page, killing the DOM this test inspects afterward
     (empirically confirmed).
  2. The form is still submitted for real — `page.route` only observes/
     aborts requests, it never fakes a 2xx response — so the create POST is
     a genuine round trip against `live_server` and the DB writes it
     produces are real (asserted via the Django ORM below).
  3. A persisted `pageshow` is dispatched synthetically
     (`new PageTransitionEvent('pageshow', { persisted: true })`) — the
     same signal a genuine bfcache restore fires.

Because the destination URL is the only thing this technique can observe,
it cannot distinguish `location.assign` from `location.replace` — both
produce an identical document request. That distinction (WED §5-2:
`assign` for the original successful submit's navigation, `replace` only
from the pageshow restore's forced-forward, so restores don't keep
stacking history entries) is owned by `api.js`'s source
(`commitAndNavigate` vs. the `pageshow` listener) and the Browser
Interaction Reviewer's post-implementation verdict — these e2e tests only
pin the destination, the no-re-arm guarantee, and the no-duplicate-POST
guarantee.

A **real** `page.go_back()` cannot be used for the red/green check in this
environment: it triggers a fresh server reload instead of an actual bfcache
restore (documented in `test_bfcache_loading_reset_e2e.py`'s docstring), so
it would silently produce a false green — the JS-added `.is-loading` /
marker state gets wiped by the reload itself, before the code under test
ever runs.
"""
import io

import PIL.Image
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _wait_until(page, predicate, timeout_ms=5000, interval_ms=50):
    """Poll a Python-side predicate (e.g. a route handler's captured-request
    list) until it's true. Not `page.wait_for_function` — that evaluates JS
    in the browser and can't see state that only exists on the Python side
    (route handler callbacks run here, not in-page). Mirrors this
    directory's existing `page.wait_for_timeout(...)` polling idiom (e.g.
    test_carousel_reduced_motion_e2e.py), just wrapped in a condition
    instead of a fixed sleep.
    """
    waited = 0
    while not predicate():
        if waited >= timeout_ms:
            raise TimeoutError(f"condition not met within {timeout_ms}ms")
        page.wait_for_timeout(interval_ms)
        waited += interval_ms


# window.TakuAPI.post replaced with a promise that never resolves — pins the
# request in flight indefinitely (same technique as
# test_status_sibling_focus_e2e.py's STUB_POST), so the submit button stays
# .is-loading + disabled with no marker, deterministically, instead of
# racing a real response.
STUB_POST_NEVER_RESOLVES = """
() => {
  window.TakuAPI.post = function () {
    return new Promise(function () { /* intentionally never resolves */ });
  };
}
"""


def _dispatch_persisted_pageshow(page):
    page.evaluate(
        "() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))"
    )


def _png_bytes():
    buf = io.BytesIO()
    PIL.Image.new("RGB", (10, 10), color=(0, 200, 120)).save(buf, format="PNG")
    return buf.getvalue()


class TestBfcacheCommittedSubmitForcesForward:
    def test_커밋된_페이지가_bfcache로_복원되면_재무장_없이_목록으로_강제_전진한다(
        self, live_server, page, seed, login
    ):
        from archive.models import CollectionItem

        post_requests = []
        nav_attempts = []

        def handle_api(route, request):
            if request.method == "POST":
                post_requests.append(request)
            route.continue_()

        def handle_nav(route, request):
            # Aborting the document request (not the whole route — other
            # resource types must pass through untouched) leaves the current
            # page alive instead of tearing down the marker/disabled state
            # this test inspects after the abort, while still recording
            # proof a navigation to this destination was attempted. Must use
            # the "aborted" error code (ERR_ABORTED, cancellation semantics)
            # — the default "failed" code replaces the main-frame document
            # with a chrome-error page, killing the very DOM this test
            # inspects afterward (empirically confirmed).
            if request.resource_type == "document":
                nav_attempts.append(request.url)
                route.abort("aborted")
            else:
                route.continue_()

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/new/")
        page.route("**/api/collection-items/", handle_api)
        page.route("**/collection/", handle_nav)

        page.fill("#collection-name", "강제 전진 테스트 굿즈")
        submit_btn = page.locator('#collection-create-form button[type="submit"]')
        submit_btn.click()

        # The first aborted document request to /collection/ is
        # commitAndNavigate's own assign() firing after the real 201 — its
        # marker-then-navigate ordering (api.js:390-395) is what this wait
        # is standing in for.
        _wait_until(page, lambda: len(nav_attempts) >= 1)

        assert len(post_requests) == 1
        assert submit_btn.get_attribute("data-committed-redirect") == "/collection/"
        assert (
            CollectionItem.objects.filter(
                user=seed.user, name="강제 전진 테스트 굿즈"
            ).count()
            == 1
        )

        _dispatch_persisted_pageshow(page)

        # A second aborted document request to the same destination is the
        # pageshow handler's marker branch forcing the page on — the
        # observable proxy for its location.replace(...) call (see module
        # docstring for why assign vs. replace itself is out of this
        # technique's reach).
        _wait_until(page, lambda: len(nav_attempts) >= 2)
        assert nav_attempts[:2] == [f"{live_server.url}/collection/"] * 2
        expect(submit_btn).to_be_disabled()

        # No re-arm means no way to fire a second POST through this button —
        # confirmed directly: still exactly one captured request, one row.
        assert len(post_requests) == 1
        assert (
            CollectionItem.objects.filter(
                user=seed.user, name="강제 전진 테스트 굿즈"
            ).count()
            == 1
        )


class TestBfcacheIncompleteSubmitStillRearms:
    def test_미완_요청으로_복원된_페이지는_기존대로_버튼이_재활성화된다(
        self, live_server, page, seed, login
    ):
        # Negative-contract guard for the fix above: a submit that never
        # got a response (no success, no marker) must still be recovered by
        # the existing api.js pageshow contract
        # (test_bfcache_loading_reset_e2e.py) — the commit-marker branch
        # must never swallow the unmarked case.
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/new/")

        page.evaluate(STUB_POST_NEVER_RESOLVES)
        page.fill("#collection-name", "미완 요청 테스트 굿즈")
        submit_btn = page.locator('#collection-create-form button[type="submit"]')
        submit_btn.click()

        expect(submit_btn).to_be_disabled()
        assert submit_btn.evaluate("el => el.classList.contains('is-loading')")
        assert submit_btn.get_attribute("data-committed-redirect") is None

        _dispatch_persisted_pageshow(page)

        expect(submit_btn).to_be_enabled()
        assert not submit_btn.evaluate("el => el.classList.contains('is-loading')")
        # No forced navigation happened either — an unmarked restore must
        # leave the user on the same page they were filling out.
        assert page.url == f"{live_server.url}/collection/new/"


class TestBfcachePartialPhotoFailureAllowsRetry:
    def test_사진_일부_실패_후_복원되면_강제_전진_없이_재시도가_가능하다(
        self, live_server, page, seed, login
    ):
        # WED §5-2 boundary condition ①: the commit marker must never be
        # applied to a partial-failure branch that leaves the page for the
        # user to retry from — visit_create.js's partial-photo-failure path
        # (record saved, some photos failed) is exactly that branch. Only
        # the record-create POST succeeds for real; the second photo upload
        # is synthetically failed so the flow actually reaches that branch.
        from archive.models import VisitRecord

        call_count = {"n": 0}
        nav_attempts = []

        def handle_photo(route, request):
            call_count["n"] += 1
            if call_count["n"] == 1:
                route.continue_()
            else:
                route.fulfill(
                    status=500,
                    content_type="application/json",
                    body='{"detail": "synthetic photo upload failure"}',
                )

        def handle_nav(route, request):
            # Same technique as INTG-FE-01: abort only the document request,
            # with the "aborted" error code (see that class's handle_nav for
            # why "failed" would replace the page with a chrome-error page),
            # so a wrongly-fired commitAndNavigate is observable without
            # tearing down the page this test inspects afterward.
            if request.resource_type == "document":
                nav_attempts.append(request.url)
                route.abort("aborted")
            else:
                route.continue_()

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/visits/new/")
        page.route("**/api/visit-records/*/photos/", handle_photo)
        page.route("**/archive/visits/", handle_nav)

        # events[1] ("겨울 콜라보 카페"), not events[0]: seed
        # (tests/e2e/conftest.py) pre-creates a VisitRecord against
        # events[0], which would make the post-submit count below 2, not 1.
        page.select_option("#visit-subject", f"event:{seed.events[1].id}")
        page.fill("#visit-date", "2026-06-20")
        page.locator("#visit-photos").set_input_files(
            [
                {"name": "photo1.png", "mimeType": "image/png", "buffer": _png_bytes()},
                {"name": "photo2.png", "mimeType": "image/png", "buffer": _png_bytes()},
            ]
        )

        submit_btn = page.locator('#visit-create-form button[type="submit"]')
        submit_btn.click()

        # The partial-failure branch only runs once the 2nd photo's request
        # actually settles — revealContinueLink() (visible "방문 기록
        # 목록으로 이동" link) is the observable proof of reaching it, since
        # setLoading(false) is never called on this branch (the button stays
        # .is-loading on purpose — see visit_create.js's partial-success
        # comment) and would otherwise be indistinguishable from a
        # still-uploading state.
        expect(page.locator("#visit-continue-link")).to_be_visible()
        assert VisitRecord.objects.filter(user=seed.user, event=seed.events[1]).count() == 1

        # Boundary ①: this is a recoverable retry state, not a committed
        # one — no marker, and the button must still read as in-flight.
        assert submit_btn.get_attribute("data-committed-redirect") is None
        assert submit_btn.evaluate("el => el.classList.contains('is-loading')")
        expect(submit_btn).to_be_disabled()

        _dispatch_persisted_pageshow(page)

        # Unmarked restore → existing recovery contract re-arms the button
        # (retry is possible) and never forces navigation away: zero document
        # requests to the list URL, and the page itself never left.
        expect(submit_btn).to_be_enabled()
        assert not submit_btn.evaluate("el => el.classList.contains('is-loading')")
        assert nav_attempts == []
        assert page.url == f"{live_server.url}/archive/visits/new/"
