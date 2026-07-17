"""E2E regression: the edit-page delete button must be bound by exactly one
click listener.

collection.js is one file shared by all three collection pages (list/create/
edit) — unlike the visit.js/visit_edit.js sibling pair, which never coexist
on the same page because they live in separate files. Both the list card and
the edit page render a button with the same data-delete-item-id attribute
(team lead's convention correction, 2026-07-16), so a naive page-scoped
binder for each context would double-bind the edit page's single button:
once from a list-page-wide binder, once from an edit-page-scoped one.
bindItemDeletes()'s single querySelectorAll + per-button dataset.deleteBound
guard is what prevents this — this test locks that guarantee in.

Asserts on TakuConfirm invocation count, not DELETE request count. Verified
empirically while writing this test (temporarily re-introducing the
double-bind, then reverting — see the C5b-2 changelog entry): under a
double-bind, exactly one DELETE request still reaches the network, because
TakuConfirm is a singleton overlay (confirm-modal.js) that resolves an
already-pending confirm false the instant a second call opens its own — the
first-bound listener's confirm gets silently cancelled, and only the
second-bound listener's confirm (the one the test's real click resolves)
proceeds to DELETE. A DELETE-count assertion alone would not have caught
this defect; every bound listener does call TakuConfirm synchronously before
that cancellation can happen, which is why that call count is the signal
that actually distinguishes one binding from two.

This masking effect is latent, not a live defect: bindItemDeletes()'s
dataset.deleteBound guard currently prevents any double-bind from ever
occurring, so no user sees a duplicate confirm, a duplicate DELETE, or an
incorrect "already deleted" error today. The risk only resurfaces if that
guard is later removed or bypassed — this test exists to catch exactly that
regression, since a DELETE-count assertion would stay green even after the
guard breaks.
"""
import pytest

pytestmark = pytest.mark.e2e


class TestCollectionDeleteSingleBinding:
    def test_수정_페이지_삭제_버튼을_클릭하면_확인_대화상자가_정확히_한_번만_호출되고_삭제된다(
        self, live_server, page, seed, login
    ):
        from archive.models import CollectionItem

        item = CollectionItem.objects.create(user=seed.user, name="삭제 단일 바인딩 테스트")

        confirm_calls = []
        page.on(
            "console",
            lambda msg: confirm_calls.append(msg.text)
            if msg.text == "__TAKUCONFIRM_CALLED__"
            else None,
        )

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/collection/{item.id}/edit/")

        # Wrap TakuConfirm to log a marker on every invocation without
        # changing its behavior — still delegates to the real
        # implementation, so the confirm dialog and the click flow below
        # work exactly as they would in production.
        page.evaluate(
            """() => {
                var original = window.TakuConfirm;
                window.TakuConfirm = function (message) {
                    console.log('__TAKUCONFIRM_CALLED__');
                    return original(message);
                };
            }"""
        )

        page.click('[data-delete-item-id]')
        page.click(".confirm-yes")
        page.wait_for_url(f"{live_server.url}/collection/")

        assert len(confirm_calls) == 1
        assert not CollectionItem.objects.filter(pk=item.id).exists()
