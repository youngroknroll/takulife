import pytest

from events.models import Event


@pytest.mark.django_db
def test_public_event_list_is_available(client):
    response = client.get("/api/events/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_public_event_list_returns_only_published_events(client):
    published = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    Event.objects.create(title="Draft event", publish_status=Event.PublishStatus.DRAFT)

    response = client.get("/api/events/")

    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["id"] == published.id


@pytest.mark.django_db
def test_public_event_detail_returns_published_event(client):
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get(f"/api/events/{event.id}/")

    assert response.status_code == 200
    assert response.json()["id"] == event.id
    assert response.json()["title"] == "Published event"


@pytest.mark.django_db
def test_public_event_detail_hides_unpublished_event(client):
    event = Event.objects.create(title="Draft event", publish_status=Event.PublishStatus.DRAFT)

    response = client.get(f"/api/events/{event.id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_public_event_list_filters_by_q(client):
    matching = Event.objects.create(title="Seoul popup event", publish_status=Event.PublishStatus.PUBLISHED)
    Event.objects.create(title="Busan cafe event", publish_status=Event.PublishStatus.PUBLISHED)

    response = client.get("/api/events/", {"q": "popup"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_filters_by_region(client):
    matching = Event.objects.create(
        title="Seoul event",
        region="seoul",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    Event.objects.create(
        title="Busan event",
        region="busan",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/", {"region": "seoul"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_filters_by_category(client):
    matching = Event.objects.create(
        title="Popup event",
        category="popup_store",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    Event.objects.create(
        title="Cafe event",
        category="collaboration_cafe",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get("/api/events/", {"category": "popup_store"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [matching.id]


@pytest.mark.django_db
def test_public_event_list_combines_q_region_and_category_filters(client):
    matching = Event.objects.create(
        title="Seoul popup event",
        category="popup_store",
        region="seoul",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    Event.objects.create(
        title="Seoul cafe event",
        category="collaboration_cafe",
        region="seoul",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    Event.objects.create(
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
def test_public_event_response_uses_category_and_hides_publish_status(client):
    event = Event.objects.create(
        title="Popup event",
        category="popup_store",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    response = client.get(f"/api/events/{event.id}/")

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "popup_store"
    assert "publish_status" not in body
