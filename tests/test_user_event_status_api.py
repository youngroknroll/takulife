import pytest

from events.models import Event


@pytest.mark.parametrize(
    ("method", "path_template", "payload"),
    [
        ("put", "/api/me/event-statuses/{event_id}/", {"status": "interested"}),
        ("post", "/api/user-event-statuses/", {"event": "{event_id}", "status": "interested"}),
    ],
)
@pytest.mark.django_db
def test_archive_user_event_status_routes_remain_inactive(
    client,
    django_user_model,
    method,
    path_template,
    payload,
):
    user = django_user_model.objects.create_user(username="status-user", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    path = path_template.format(event_id=event.id)
    request_payload = {
        key: (event.id if value == "{event_id}" else value)
        for key, value in payload.items()
    }
    response = getattr(client, method)(
        path,
        request_payload,
        content_type="application/json",
    )

    assert response.status_code == 404
