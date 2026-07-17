"""E2E regression: hscroll (home discovery rows) and photo-carousel (visit
card photo gallery) arrow buttons meet the §5.4 44px touch target.

Desktop hscroll-btn (36px) and the visit-card carousel-btn (34px) are
visually enlarged to 44px directly — both are `position: absolute` overlay
circles with no document-flow neighbors, so growing them doesn't risk any
reflow/wrap.

Mobile hscroll-btn keeps its intentionally smaller 30px visual circle (an
existing overlay-crowding trade-off, hscroll.css) — the button's own box
grows to the full 44px hit area instead, with the visible circle painted on
a centered ::before. A plain `getBoundingClientRect()` on the button already
covers this (the hit area *is* the button's own box, not an overflowing
pseudo-element), so no separate "effective tap area" measurement technique
is needed — this suite additionally clicks the edge of that grown box
(outside the visible 30px circle) to prove the extra 14px is genuinely
clickable, not just wide on paper.
"""
import io

import pytest
import PIL.Image
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import VisitRecord, VisitRecordPhoto

pytestmark = pytest.mark.e2e


def _png_bytes():
    buf = io.BytesIO()
    PIL.Image.new("RGB", (10, 10), color=(200, 40, 40)).save(buf, format="PNG")
    return buf.getvalue()


class TestHscrollDesktopArrowTouchTarget:
    def test_데스크톱_hscroll_화살표_버튼은_44px_이상의_터치_타깃을_가진다(self, live_server, page, seed):
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(live_server.url + "/")

        box = page.locator(".hscroll-btn").first.bounding_box()
        assert box["width"] >= 44
        assert box["height"] >= 44


class TestHscrollMobileArrowHitArea:
    def test_모바일_hscroll_화살표는_44px_히트_영역을_가지고_시각적_원_밖_가장자리를_클릭해도_스크롤된다(
        self, live_server, page, seed
    ):
        page.set_viewport_size({"width": 375, "height": 900})
        page.goto(live_server.url + "/")

        track = page.locator("[data-hscroll-track]").first
        track.scroll_into_view_if_needed()
        page.evaluate("(el) => { el.scrollLeft = 200; }", track.element_handle())
        # scroll-snap-type: x mandatory (mobile) settles the assigned 200 to
        # the nearest snap point almost immediately (observed ~190, not
        # 200) — wait for that drift to finish before taking the baseline,
        # so the post-click assertion isn't measuring snap noise instead of
        # an actual click.
        page.wait_for_timeout(200)
        baseline = page.evaluate("(el) => el.scrollLeft", track.element_handle())

        prev_btn = page.locator(".hscroll-prev.hscroll-btn").first
        prev_btn.scroll_into_view_if_needed()
        box = prev_btn.bounding_box()
        # The button's own box is the hit area (no overflowing pseudo-element
        # involved), so this bounding box already *is* the tappable region.
        assert box["width"] >= 44
        assert box["height"] >= 44

        # Click 1px from the box's left edge — outside the visible 30px
        # circle (which starts 4px in), inside the extra hit area only. This
        # pixel sits inside .hscroll-wrap's clip region only because the
        # button's own box is flush against the wrap edge (left: 0) — an
        # earlier -3px inset pushed this same relative pixel outside the
        # wrap's overflow:hidden clip, where it silently missed every click.
        edge_x = box["x"] + 1
        edge_y = box["y"] + box["height"] / 2
        page.mouse.click(edge_x, edge_y)
        page.wait_for_timeout(400)

        scroll_left = page.evaluate("(el) => el.scrollLeft", track.element_handle())
        # A real "prev" click jumps by roughly a card width (observed: to 0
        # from a ~190 baseline) — a threshold well below the baseline, not
        # just "< baseline", so snap-settling noise alone can't satisfy it.
        assert scroll_left < baseline - 50


class TestPhotoCarouselArrowTouchTarget:
    def test_방문_기록_사진_캐러셀_화살표_버튼은_44px_이상의_터치_타깃을_가진다(self, live_server, page, seed, login):
        visit = VisitRecord.objects.create(
            user=seed.user, event=seed.events[0], visited_on="2026-06-16"
        )
        for _ in range(2):
            VisitRecordPhoto.objects.create(
                visit_record=visit,
                image=SimpleUploadedFile("photo.png", _png_bytes(), content_type="image/png"),
            )

        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(f"{live_server.url}/archive/visits/")

        box = page.locator(".carousel-btn").first.bounding_box()
        assert box["width"] >= 44
        assert box["height"] >= 44
