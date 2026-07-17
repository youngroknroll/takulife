"""E2E regression: the home collection-snapshot panel's (H-2) initial-state
recovery CTAs (.empty-action, reusing the IA-2/D6 pattern) meet the §5.4
44px touch target — cards.css's blanket min-height:44px fix verified here on
its newest render site (BIR IA-2 MEDIUM backlog item, resolved).
"""
import pytest

pytestmark = pytest.mark.e2e


class TestHomeSnapshotCtaTouchTarget:
    def test_empty_state_ctas_meet_min_height(self, live_server, page, seed, login):
        # The plain seeded user has no CollectionItem/visited/upcoming-planned
        # data (seed's own planned events carry no start_date, so they never
        # qualify as "upcoming") — snapshot_active is False, landing on the
        # initial empty state without any extra seeding.
        login(page, live_server.url, "e2e_user@example.com", seed.password)
        page.goto(live_server.url + "/")

        boxes = page.locator(".snapshot-panel .empty-action").all()
        assert len(boxes) == 2
        for box in boxes:
            bounding = box.bounding_box()
            assert bounding["height"] >= 44
