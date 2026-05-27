import pytest


@pytest.mark.django_db
def test_admin_can_create_event_draft_from_url(admin_client):
    response = admin_client.post("/api/admin/event-drafts/", {"source_url": "https://example.com/event"})

    assert response.status_code == 201
