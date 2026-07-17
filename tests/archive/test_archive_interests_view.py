"""archive_interests page view — SSR rendering, not the JSON API
(moved from tests/archive/test_event_interest_api.py)."""

import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_사용자가_관심_등록한_행사는_아카이브_관심_목록_페이지에_표시된다(client, make_user, make_event, make_interest):
    user = make_user(username="interests-page-user")
    event = make_event(title="Page Event")
    make_interest(user, event=event)

    client.force_login(user)
    response = client.get("/archive/interests/")

    assert response.status_code == 200
    assert str(event.id).encode() in response.content


@pytest.mark.django_db
def test_비로그인_사용자가_아카이브_관심_목록_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get("/archive/interests/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
