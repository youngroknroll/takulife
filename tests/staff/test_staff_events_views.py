"""staff.views.staff_events — PR-E1 (/staff/events/ list + quality drilldown).

Covers the staff_console_required gate (auth pin, mirrors test_staff_console.py
conventions) and the warning/publish_status filtering + pagination the view
delegates to events.queries.list_staff_events.
"""
from datetime import date, timedelta

import pytest

from events.models import Event


@pytest.mark.django_db
def test_anonymous_redirects_to_login(client):
    resp = client.get("/staff/events/")

    assert resp.status_code == 302
    assert resp.url == "/accounts/login/?next=/staff/events/"


@pytest.mark.django_db
def test_non_staff_returns_403(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/events/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_staff_can_access_events_list(staff_client, make_event):
    staff, client = staff_client()
    make_event(title="공개 행사")

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    assert "공개 행사" in resp.content.decode()


@pytest.mark.django_db
def test_events_list_includes_draft_events_by_default(staff_client, make_draft_event):
    staff, client = staff_client()
    make_draft_event(title="비공개 초안", official_url=None)

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    assert "비공개 초안" in resp.content.decode()


@pytest.mark.django_db
def test_warning_filter_scopes_rows_to_matching_events(staff_client, make_event):
    staff, client = staff_client()
    make_event(title="URL 없는 행사", official_url=None)
    make_event(
        title="깨끗한 행사",
        official_url="https://example.com/clean",
        region="서울",
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
    )

    resp = client.get("/staff/events/?warning=missing_official_url")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "URL 없는 행사" in content
    assert "깨끗한 행사" not in content
    assert resp.context["selected_warning"] == "missing_official_url"


@pytest.mark.django_db
def test_unknown_warning_falls_back_to_no_filter(staff_client, make_event):
    staff, client = staff_client()
    make_event(title="아무 행사")

    resp = client.get("/staff/events/?warning=not-a-real-warning")

    assert resp.status_code == 200
    assert resp.context["selected_warning"] == ""
    assert "아무 행사" in resp.content.decode()


@pytest.mark.django_db
def test_publish_status_filter_restricts_rows(staff_client, make_event, make_draft_event):
    staff, client = staff_client()
    make_event(title="게시된 행사")
    make_draft_event(title="초안 행사", official_url=None)

    resp = client.get("/staff/events/?publish_status=draft")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "초안 행사" in content
    assert "게시된 행사" not in content
    assert resp.context["selected_publish_status"] == "draft"


@pytest.mark.django_db
def test_pagination_second_page(staff_client, make_event):
    from events.queries import STAFF_EVENT_LISTING_PAGE_SIZE

    staff, client = staff_client()
    for i in range(STAFF_EVENT_LISTING_PAGE_SIZE + 1):
        make_event(title=f"행사 {i}")

    resp = client.get("/staff/events/?page=2")

    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2
    assert len(resp.context["page_obj"].object_list) == 1


@pytest.mark.django_db
def test_ended_still_published_warning_uses_server_today(staff_client, make_event):
    staff, client = staff_client()
    make_event(
        title="종료된 행사",
        official_url="https://example.com/ended",
        end_date=date.today() - timedelta(days=1),
    )
    make_event(
        title="진행중 행사",
        official_url="https://example.com/ongoing",
        end_date=date.today() + timedelta(days=1),
    )

    resp = client.get("/staff/events/?warning=ended_still_published")

    content = resp.content.decode()
    assert "종료된 행사" in content
    assert "진행중 행사" not in content
