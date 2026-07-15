"""E2E regression: collection.js's create-form double-submit guard.

TakuAPI.setLoading(submitBtn, true) sets button.disabled synchronously,
before the handler's first await — a second click/Enter arriving after that
point should never reach the network, since a disabled button does not
dispatch a fresh click (browser-level, not a JS listener guard). No
CollectionItem has a uniqueness constraint (collection domain design plan
§6-b), so a duplicate request would silently create two rows rather than
erroring — this test is the only guard against that.
"""
import pytest

pytestmark = pytest.mark.e2e


class TestCollectionCreateDoubleSubmit:
    def test_double_click_sends_one_request_and_creates_one_item(
        self, live_server, page, seed, login
    ):
        from archive.models import CollectionItem

        post_requests = []

        def handle(route, request):
            if request.method == "POST":
                post_requests.append(request)
            route.continue_()

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/collection/new/")
        page.route("**/api/collection-items/", handle)

        page.fill("#collection-name", "더블클릭 테스트 굿즈")

        # Two native clicks dispatched back to back in a single JS task —
        # the first click's synchronous handler prefix (through
        # setLoading(true)) completes before the second click is processed,
        # so the second click hits an already-disabled button and is a
        # native no-op (not a JS-level guard being tested here).
        page.evaluate(
            """() => {
                var btn = document.querySelector('#collection-create-form button[type="submit"]');
                btn.click();
                btn.click();
            }"""
        )

        page.wait_for_url(f"{live_server.url}/archive/collection/")

        assert len(post_requests) == 1
        assert (
            CollectionItem.objects.filter(
                user=seed.user, name="더블클릭 테스트 굿즈"
            ).count()
            == 1
        )
