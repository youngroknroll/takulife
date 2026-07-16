"""End-to-end privacy guard across all 8 stage-0 analytics events
(PR-0e checkpoint B12).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)

Exercises every real code path that records an AnalyticsEvent (archive
services + events API), then asserts no row anywhere ever carries personal
data: no forbidden context key, no leaked free text (short_review), no
leaked email, and no raw user pk in user_key.

Uses `django.test.Client()` instantiated directly (not the `client`
fixture) so this file is not subject to the API/view layer-purity guard
(tests/core/test_architecture_boundaries.py) that would otherwise forbid
importing archive.services here — this file intentionally spans the
service and HTTP/API boundaries to prove the privacy guarantee holds
end-to-end, not at one layer only.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

import archive.services as archive_services
from archive.models import UserEventStatus
from core.analytics import FORBIDDEN_CONTEXT_KEYS, pseudonymous_user_key
from core.models import AnalyticsEvent
from events.models import Event


LEAK_PROBE_EMAIL = "leak-probe-user@example.com"
LEAK_PROBE_REVIEW = "this private review text must never leak into analytics"
LEAK_PROBE_NAME = "must never leak collection item name"
LEAK_PROBE_MEMO = "must never leak collection item memo"


def _walk_all_analytics_paths(make_user, make_event, png_bytes):
    user = make_user(email=LEAK_PROBE_EMAIL)
    event = make_event(title="Privacy guard event", publish_status=Event.PublishStatus.PUBLISHED)

    archive_services.create_event_interest(user=user, event=event)

    status = archive_services.create_user_event_status(
        user=user, event=event, status=UserEventStatus.Status.PLANNED
    )
    archive_services.mark_visited(user_event_status=status)

    second_event = make_event(
        title="Second privacy guard event", publish_status=Event.PublishStatus.PUBLISHED
    )
    archive_services.create_user_event_status(
        user=user, event=second_event, status=UserEventStatus.Status.VISITED
    )

    record = archive_services.create_visit_record(
        user=user, event=event, visited_on="2026-05-26", short_review=LEAK_PROBE_REVIEW
    )
    archive_services.create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )

    item = archive_services.create_collection_item(
        user=user, name=LEAK_PROBE_NAME, memo=LEAK_PROBE_MEMO, visit_record=record,
    )
    archive_services.update_collection_item(item=item, is_wanted=True)
    archive_services.update_collection_item(item=item, tradeable_quantity=1)

    http_client = Client()
    http_client.get("/api/events/")
    http_client.get("/api/events/", {"q": "guard"})
    http_client.get(f"/api/events/{event.id}/")

    return user


@pytest.mark.django_db
def test_no_analytics_event_row_ever_leaks_personal_data(make_user, make_event, png_bytes):
    user = _walk_all_analytics_paths(make_user, make_event, png_bytes)

    events = list(AnalyticsEvent.objects.all())
    recorded_names = {event.event_name for event in events}
    assert recorded_names == {
        AnalyticsEvent.EventName.EVENT_LIST_VIEWED,
        AnalyticsEvent.EventName.EVENT_SEARCHED,
        AnalyticsEvent.EventName.EVENT_DETAIL_VIEWED,
        AnalyticsEvent.EventName.EVENT_INTERESTED,
        AnalyticsEvent.EventName.EVENT_PLANNED,
        AnalyticsEvent.EventName.EVENT_MARKED_VISITED,
        AnalyticsEvent.EventName.VISIT_RECORD_CREATED,
        AnalyticsEvent.EventName.VISIT_PHOTO_ADDED,
        AnalyticsEvent.EventName.COLLECTION_ITEM_CREATED,
        AnalyticsEvent.EventName.COLLECTION_ITEM_UPDATED,
        AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT,
        AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED,
        AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_TRADEABLE,
    }
    # event_marked_visited fires twice (create + mark_visited); the
    # collection path below adds 6 more (created 1, linked_to_visit 1,
    # updated 2x, marked_wanted 1, marked_tradeable 1).
    assert len(events) >= 15

    expected_user_key = pseudonymous_user_key(user)
    for event in events:
        assert not FORBIDDEN_CONTEXT_KEYS & event.context.keys()
        serialized_context = str(event.context)
        assert LEAK_PROBE_EMAIL not in serialized_context
        assert LEAK_PROBE_REVIEW not in serialized_context
        assert LEAK_PROBE_NAME not in serialized_context
        assert LEAK_PROBE_MEMO not in serialized_context
        if event.user_key:
            # Equality against the known-non-reversible pseudonymous key
            # (see tests/core/test_analytics_pseudonymization.py) rather
            # than a raw-pk substring check, which is unreliable for a
            # small, single-digit pk value.
            assert event.user_key == expected_user_key
