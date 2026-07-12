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
    def test_desktop_arrow_meets_min_height(self, live_server, page, seed):
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(live_server.url + "/")

        box = page.locator(".hscroll-btn").first.bounding_box()
        assert box["width"] >= 44
        assert box["height"] >= 44


class TestHscrollMobileArrowHitArea:
    def test_mobile_arrow_hit_box_meets_min_height_and_edge_is_clickable(
        self, live_server, page, seed
    ):
        page.set_viewport_size({"width": 375, "height": 900})
        page.goto(live_server.url + "/")

        track = page.locator("[data-hscroll-track]").first
        track.scroll_into_view_if_needed()
        page.evaluate("(el) => { el.scrollLeft = 200; }", track.element_handle())

        prev_btn = page.locator(".hscroll-prev.hscroll-btn").first
        prev_btn.scroll_into_view_if_needed()
        box = prev_btn.bounding_box()
        # The button's own box is the hit area (no overflowing pseudo-element
        # involved), so this bounding box already *is* the tappable region.
        assert box["width"] >= 44
        assert box["height"] >= 44

        # Click 3px from the box's left edge — outside the old 30px visible
        # circle (which starts 7px in), inside the new 44px hit area only.
        edge_x = box["x"] + 3
        edge_y = box["y"] + box["height"] / 2
        page.mouse.click(edge_x, edge_y)
        page.wait_for_timeout(400)

        scroll_left = page.evaluate("(el) => el.scrollLeft", track.element_handle())
        assert scroll_left < 200


class TestPhotoCarouselArrowTouchTarget:
    def test_carousel_arrow_meets_min_height(self, live_server, page, seed, login):
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
