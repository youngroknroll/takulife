import pytest
from datetime import timedelta
from django.utils import timezone

from events.models import Event


@pytest.mark.django_db
def test_public_event_list_is_available(client):
    response = client.get("/api/events/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_public_event_list_returns_only_published_events(client, make_event):
    published = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    make_event(title="Draft event", publish_status=Event.PublishStatus.DRAFT)

    response = client.get("/api/events/")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["id"] == published.id


@pytest.mark.django_db
def test_public_event_detail_returns_published_event(client, make_event):
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get(f"/api/events/{event.id}/")

    assert response.status_code == 200
    assert response.json()["id"] == event.id
    assert response.json()["title"] == "Published event"


@pytest.mark.django_db
def test_public_event_detail_hides_unpublished_event(client, make_event):
    event = make_event(title="Draft event", publish_status=Event.PublishStatus.DRAFT)

    response = client.get(f"/api/events/{event.id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_public_event_list_filters_by_q(client, make_event):
    matching = make_event(title="Seoul popup event", publish_status=Event.PublishStatus.PUBLISHED)
    make_event(title="Busan cafe event", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get("/api/events/", {"q": "popup"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_filters_by_region(client, make_event):
    matching = make_event(
        title="Seoul event",
        region="seoul",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="Busan event",
        region="busan",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/", {"region": "seoul"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_filters_by_category(client, make_event):
    matching = make_event(
        title="Popup event",
        category="popup_store",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="Cafe event",
        category="collaboration_cafe",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/", {"category": "popup_store"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_combines_q_region_and_category_filters(client, make_event):
    matching = make_event(
        title="Seoul popup event",
        category="popup_store",
        region="seoul",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="Seoul cafe event",
        category="collaboration_cafe",
        region="seoul",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="Busan popup event",
        category="popup_store",
        region="busan",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get(
        "/api/events/",
        {"q": "popup", "region": "seoul", "category": "popup_store"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_response_uses_category_and_hides_publish_status(client, make_event):
    event = make_event(
        title="Popup event",
        category="popup_store",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get(f"/api/events/{event.id}/")

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "popup_store"
    assert "publish_status" not in body


@pytest.mark.django_db
def test_public_event_list_filters_by_start_date_from(client, make_event):
    matching = make_event(
        title="June event",
        start_date="2026-06-01",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="May event",
        start_date="2026-05-31",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/", {"start_date_from": "2026-06-01"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_filters_by_start_date_to(client, make_event):
    matching = make_event(
        title="May event",
        start_date="2026-05-31",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="June event",
        start_date="2026-06-01",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/", {"start_date_to": "2026-05-31"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_filters_by_status_upcoming_ongoing_ended(client, make_event):
    today = timezone.localdate()
    upcoming = make_event(
        title="Upcoming event",
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=2),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    ongoing = make_event(
        title="Ongoing event",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=1),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    ended = make_event(
        title="Ended event",
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    upcoming_response = client.get("/api/events/", {"status": "upcoming"})
    ongoing_response = client.get("/api/events/", {"status": "ongoing"})
    ended_response = client.get("/api/events/", {"status": "ended"})

    assert upcoming_response.status_code == 200
    assert [item["id"] for item in upcoming_response.json()["results"]] == [upcoming.id]
    assert ongoing_response.status_code == 200
    assert [item["id"] for item in ongoing_response.json()["results"]] == [ongoing.id]
    assert ended_response.status_code == 200
    assert [item["id"] for item in ended_response.json()["results"]] == [ended.id]


@pytest.mark.django_db
def test_public_event_list_filters_by_status_closing_soon(client, make_event):
    today = timezone.localdate()
    closing_today = make_event(
        title="Closing today",
        start_date=today - timedelta(days=2),
        end_date=today,
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    closing_in_five_day_window = make_event(
        title="Closing in 4 days",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=4),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="Closing in 5 days",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=5),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="Upcoming only",
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=2),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="Already ended",
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/", {"status": "closing_soon"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [
        closing_today.id,
        closing_in_five_day_window.id,
    ]


@pytest.mark.django_db
def test_public_event_list_rejects_invalid_status_filter(client, make_event):
    first = make_event(title="First", publish_status=Event.PublishStatus.PUBLISHED)
    second = make_event(title="Second", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get("/api/events/", {"status": "invalid"})

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.django_db
def test_public_event_list_accepts_blank_status_filter(client, make_event):
    matching = make_event(title="Listed", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get("/api/events/", {"status": ""})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_filters_by_multiple_regions(client, make_event):
    seoul = make_event(
        title="Seoul", region="seoul", publish_status=Event.PublishStatus.PUBLISHED
    )
    gyeonggi = make_event(
        title="Gyeonggi", region="gyeonggi", publish_status=Event.PublishStatus.PUBLISHED
    )
    make_event(
        title="Busan", region="busan", publish_status=Event.PublishStatus.PUBLISHED
    )

    response = client.get("/api/events/?region=seoul&region=gyeonggi")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["results"]}
    assert ids == {seoul.id, gyeonggi.id}


@pytest.mark.django_db
def test_public_event_list_filters_by_category_work_title_and_start_date_range(client, make_event):
    matching = make_event(
        title="June popup",
        category="popup_store",
        work_title="Gundam",
        start_date="2026-06-10",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="June cafe",
        category="collaboration_cafe",
        work_title="Gundam",
        start_date="2026-06-10",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="July popup",
        category="popup_store",
        work_title="Gundam",
        start_date="2026-07-01",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    make_event(
        title="June popup no-work-match",
        category="popup_store",
        work_title="One Piece",
        start_date="2026-06-10",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get(
        "/api/events/",
        {
            "category": "popup_store",
            "work_title": "gundam",
            "start_date_from": "2026-06-01",
            "start_date_to": "2026-06-30",
        },
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_reversed_start_date_range_returns_empty_results(client, make_event):
    make_event(
        title="June event",
        start_date="2026-06-10",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get(
        "/api/events/",
        {"start_date_from": "2026-06-30", "start_date_to": "2026-06-01"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


@pytest.mark.django_db
def test_public_event_list_rejects_invalid_start_date_from(client, make_event):
    make_event(title="First", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get("/api/events/", {"start_date_from": "2026/06/01"})

    assert response.status_code == 400
    assert "start_date_from" in response.json()


@pytest.mark.django_db
def test_public_event_list_rejects_invalid_start_date_to(client, make_event):
    make_event(title="First", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get("/api/events/", {"start_date_to": "2026/06/30"})

    assert response.status_code == 400
    assert "start_date_to" in response.json()


@pytest.mark.parametrize("query_param", ["q", "region", "category", "work_title"])
@pytest.mark.django_db
def test_public_event_list_ignores_blank_documented_string_filters(client, query_param, make_event):
    first = make_event(title="First", publish_status=Event.PublishStatus.PUBLISHED)
    second = make_event(title="Second", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get("/api/events/", {query_param: ""})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [first.id, second.id]


@pytest.mark.django_db
def test_public_event_list_default_order_prioritizes_ongoing_then_upcoming_then_ended(client, make_event):
    today = timezone.localdate()
    ended_old = make_event(
        title="Ended long ago",
        start_date=today - timedelta(days=20),
        end_date=today - timedelta(days=10),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    upcoming_later = make_event(
        title="Upcoming later start",
        start_date=today + timedelta(days=4),
        end_date=today + timedelta(days=5),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    ongoing_later = make_event(
        title="Ongoing later end",
        start_date=today - timedelta(days=3),
        end_date=today + timedelta(days=3),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    ended_recent = make_event(
        title="Ended recently",
        start_date=today - timedelta(days=5),
        end_date=today - timedelta(days=1),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    upcoming_soon = make_event(
        title="Upcoming soon start",
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=2),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    ongoing_soon = make_event(
        title="Ongoing soon end",
        start_date=today - timedelta(days=2),
        end_date=today + timedelta(days=1),
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [
        ongoing_soon.id,
        ongoing_later.id,
        upcoming_soon.id,
        upcoming_later.id,
        ended_recent.id,
        ended_old.id,
    ]


@pytest.mark.django_db
def test_public_event_list_places_null_date_events_after_ranked_events(client, make_event):
    today = timezone.localdate()
    null_date = make_event(
        title="Undated event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    ended = make_event(
        title="Ended event",
        start_date=today - timedelta(days=2),
        end_date=today - timedelta(days=1),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    upcoming = make_event(
        title="Upcoming event",
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=2),
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    ongoing = make_event(
        title="Ongoing event",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=1),
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [
        ongoing.id,
        upcoming.id,
        ended.id,
        null_date.id,
    ]
