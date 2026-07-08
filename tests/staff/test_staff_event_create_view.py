"""staff.views.staff_event_create — PR-E3 C (/staff/events/new/ SSR form).

Mirrors test_staff_event_edit_views.py conventions: staff_console_required
gate, GET renders a blank form, POST-PRG creates via create_published_event
(the shared publish choke-point — no alternate creation path), invariant
violations map to field errors with the POSTed values preserved, and a
success writes a StaffActionLog(event_create).
"""
import pytest

from events.models import Event
from staff.models import StaffActionLog

CREATE_URL = "/staff/events/new/"


def _valid_payload(**overrides):
    payload = {
        "title": "새 이벤트",
        "category": "popup_store",
        "work_title": "작품명",
        "location_name": "장소명",
        "region": "seoul",
        "start_date": "2026-09-01",
        "end_date": "2026-09-10",
        "official_url": "https://example.com/new-event",
        "source_name": "공식 출처",
        "summary": "요약",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_anonymous_redirects_to_login(client):
    resp = client.get(CREATE_URL)

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next={CREATE_URL}"


@pytest.mark.django_db
def test_non_staff_returns_403(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get(CREATE_URL)

    assert resp.status_code == 403


@pytest.mark.django_db
def test_get_renders_blank_form(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.get(CREATE_URL)

    assert resp.status_code == 200
    assert 'value=""' in resp.content.decode()


@pytest.mark.django_db
def test_post_creates_published_event_and_writes_audit_log(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.post(CREATE_URL, _valid_payload())

    assert resp.status_code == 302
    event = Event.objects.get(official_url="https://example.com/new-event")
    assert event.title == "새 이벤트"
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.category == "popup_store"

    log = StaffActionLog.objects.get(target_event=event)
    assert log.actor_id == staff.id
    assert log.action == StaffActionLog.Action.EVENT_CREATE


@pytest.mark.django_db
def test_post_blank_title_returns_400_with_field_error_and_does_not_create(
    client, make_user
):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.post(
        CREATE_URL,
        _valid_payload(title="   ", official_url="https://example.com/blank-title-create"),
    )

    assert resp.status_code == 400
    assert "제목" in resp.content.decode()
    assert not Event.objects.filter(official_url="https://example.com/blank-title-create").exists()


@pytest.mark.django_db
def test_post_duplicate_official_url_returns_400_with_field_error(
    client, make_user, make_event
):
    staff = make_user(is_staff=True)
    client.force_login(staff)
    make_event(title="기존 행사", official_url="https://example.com/taken-create")

    resp = client.post(
        CREATE_URL,
        _valid_payload(official_url="https://example.com/taken-create"),
    )

    assert resp.status_code == 400
    assert "공식 URL" in resp.content.decode()
    assert Event.objects.filter(official_url="https://example.com/taken-create").count() == 1


@pytest.mark.django_db
def test_list_page_links_to_create_page(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    assert CREATE_URL in resp.content.decode()
