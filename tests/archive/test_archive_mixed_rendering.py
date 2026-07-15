"""Phase 3 UI: the archive list pages (기록장 / 예정 목록 / 찜 목록) render official
Event rows and unofficial PersonalEntry rows side by side, null-safe, marking the
unofficial ones. These are view-level guards against the AttributeError that a
naive ``row.event.*`` access would raise on a personal row.
"""
import pytest


@pytest.fixture
def mixed_user(make_user, make_event, make_entry, make_status, make_interest):
    """A user holding both an official and an unofficial status + interest."""
    user = make_user(username="mixed")
    event = make_event(title="공식 팝업", location_name="서울 성수")
    entry = make_entry(user, kind="goods", title="투명 아크릴", category="굿즈")
    make_status(user, event=event, status="planned")
    make_status(user, personal_entry=entry, status="planned")
    make_interest(user, event=event)
    make_interest(user, personal_entry=entry)
    return user, event, entry


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/archive/", "/archive/statuses/"])
def test_status_pages_render_official_and_unofficial(client, mixed_user, url):
    user, event, entry = mixed_user
    client.force_login(user)

    response = client.get(url)

    assert response.status_code == 200
    body = response.content.decode()
    assert event.title in body
    assert entry.title in body
    assert "직접 등록" in body


@pytest.mark.django_db
def test_interest_page_renders_official_and_unofficial(client, mixed_user):
    user, event, entry = mixed_user
    client.force_login(user)

    response = client.get("/archive/interests/")

    assert response.status_code == 200
    body = response.content.decode()
    assert event.title in body
    assert entry.title in body
    assert "직접 등록" in body


@pytest.mark.django_db
def test_unofficial_status_has_no_public_detail_link(client, make_user, make_entry, make_status):
    """A private personal entry must not be linked to a public /events/ page."""
    user = make_user(username="no-leak-link")
    entry = make_entry(user, kind="place", title="비공식 카페")
    status = make_status(user, personal_entry=entry, status="planned")
    client.force_login(user)

    response = client.get("/archive/statuses/")

    assert response.status_code == 200
    body = response.content.decode()
    # The only detail link present should be event-based; this personal row
    # contributes no /events/<id>/ link.
    assert f"/events/{status.id}/" not in body
