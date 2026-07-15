"""E2E regression: collection.js's edit-form recovery when the item was
deleted concurrently (e.g. by another tab/session) between this page's GET
and the PATCH submit.

Retrying is never correct here — no field edit can make a gone row
patchable — so the whole form must lock (not just show an inline error the
user can keep resubmitting into the same 404), and the one remaining valid
action (back to the list) must be reachable and focused (BIR
pre-implementation criterion #4).
"""
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


class TestCollectionEdit404Recovery:
    def test_patch_404_locks_form_and_focuses_back_link(
        self, live_server, page, seed, login
    ):
        from archive.models import CollectionItem

        item = CollectionItem.objects.create(user=seed.user, name="동시 삭제 테스트 굿즈")

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/collection/{item.id}/edit/")

        # Concurrent delete: the row is gone before this page's own submit
        # reaches the server, reproducing the deterministic 404 race.
        item.delete()

        page.fill("#collection-name", "수정 시도")
        page.click('#collection-edit-form button[type="submit"]')

        expect(page.locator("#collection-edit-error")).to_contain_text("삭제된 항목입니다")

        controls = page.locator(
            "#collection-edit-form input, #collection-edit-form select, "
            "#collection-edit-form textarea, #collection-edit-form button"
        )
        count = controls.count()
        assert count > 0
        for i in range(count):
            expect(controls.nth(i)).to_be_disabled()

        back_link = page.locator("#collection-back-link")
        expect(back_link).to_be_visible()
        expect(back_link).to_have_text("목록으로 돌아가기")
        assert page.evaluate("document.activeElement.id") == "collection-back-link"
