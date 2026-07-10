"""archive_interests page view — SSR rendering, not the JSON API
(moved from tests/archive/test_event_interest_api.py)."""

import pytest


@pytest.mark.django_db
def test_archive_interests_page_renders_200(client, make_user, make_event, make_interest):
    user = make_user(username="interests-page-user")
    event = make_event(title="Page Event")
    make_interest(user, event=event)

    client.force_login(user)
    response = client.get("/archive/interests/")

    assert response.status_code == 200
    assert str(event.id).encode() in response.content


@pytest.mark.django_db
def test_archive_interests_page_unauthenticated_redirects(client):
    response = client.get("/archive/interests/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_archive_interests_page_uses_jjim_label(client, make_user, make_event, make_interest):
    user = make_user(username="interests-label-user")
    event = make_event(title="Label Event")
    make_interest(user, event=event)

    client.force_login(user)
    response = client.get("/archive/interests/")

    assert "찜 표시한 행사 목록입니다.".encode() in response.content
