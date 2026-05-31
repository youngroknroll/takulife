import pytest

from events.models import Event


@pytest.mark.django_db
def test_event_status_route_is_not_exposed_in_mvp_scope(client, django_user_model):
    user = django_user_model.objects.create_user(username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.put(
        f"/api/me/event-statuses/{event.id}/",
        {"status": "interested"},
        content_type="application/json",
    )

    assert response.status_code == 404
