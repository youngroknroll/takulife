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
