"""staff.views.staff_event_edit — PR-E2 (/staff/events/<pk>/edit/ SSR form).

Covers the staff_console_required gate (mirrors test_staff_events_views.py
conventions), GET rendering of current field values, a successful POST-PRG
that updates the event + writes a StaffActionLog(event_update), and the
invariant-violation / duplicate-url error paths mapped to field errors with
POSTed values preserved (no silent data loss on a rejected save).
"""
from datetime import date

import pytest

from events.models import Event
from staff.models import StaffActionLog


def _edit_url(event):
    return f"/staff/events/{event.pk}/edit/"


@pytest.mark.django_db
def test_anonymous_redirects_to_login(client, make_event):
    event = make_event(official_url="https://example.com/anon-edit")

    resp = client.get(_edit_url(event))

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next=/staff/events/{event.pk}/edit/"


@pytest.mark.django_db
def test_non_staff_returns_403(client, make_user, make_event):
    user = make_user()
    client.force_login(user)
    event = make_event(official_url="https://example.com/403-edit")

    resp = client.get(_edit_url(event))

    assert resp.status_code == 403


@pytest.mark.django_db
def test_get_renders_current_field_values(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(
        title="기존 제목",
        official_url="https://example.com/get-edit",
        region="seoul",
    )

    resp = client.get(_edit_url(event))

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "기존 제목" in content
    assert "https://example.com/get-edit" in content


@pytest.mark.django_db
def test_post_updates_event_and_writes_audit_log(staff_client, make_event, staff_event_payload):
    staff, client = staff_client()
    event = make_event(title="변경 전", official_url="https://example.com/edit-target")

    resp = client.post(
        _edit_url(event),
        staff_event_payload(title="수정된 제목", official_url="https://example.com/edit-target"),
    )

    assert resp.status_code == 302
    event.refresh_from_db()
    assert event.title == "수정된 제목"
    assert event.category == "popup_store"
    assert event.work_title == "작품명"
    assert event.location_name == "장소명"
    assert event.region == "seoul"
    assert event.start_date == date(2026, 9, 1)
    assert event.end_date == date(2026, 9, 10)
    assert event.official_url == "https://example.com/edit-target"
    assert event.source_name == "공식 출처"
    assert event.summary == "요약"

    log = StaffActionLog.objects.get(target_event=event)
    assert log.actor_id == staff.id
    assert log.action == StaffActionLog.Action.EVENT_UPDATE


@pytest.mark.django_db
def test_post_blank_title_returns_400_with_field_error_and_preserves_input(
    staff_client, make_event, staff_event_payload
):
    staff, client = staff_client()
    event = make_event(title="변경 전", official_url="https://example.com/blank-title-edit")

    resp = client.post(
        _edit_url(event),
        staff_event_payload(title="   ", official_url="https://example.com/blank-title-edit"),
    )

    assert resp.status_code == 400
    content = resp.content.decode()
    assert "제목" in content
    # POSTed values (not the stale DB values) are redisplayed
    assert "https://example.com/blank-title-edit" in content

    event.refresh_from_db()
    assert event.title == "변경 전"
    assert not StaffActionLog.objects.filter(target_event=event).exists()


@pytest.mark.django_db
def test_post_blank_official_url_returns_400_with_field_error(
    staff_client, make_event, staff_event_payload
):
    staff, client = staff_client()
    event = make_event(title="변경 전", official_url="https://example.com/blank-url-edit")

    resp = client.post(
        _edit_url(event),
        staff_event_payload(title="수정된 제목", official_url="   "),
    )

    assert resp.status_code == 400
    assert "공식 URL" in resp.content.decode()
    event.refresh_from_db()
    assert event.official_url == "https://example.com/blank-url-edit"


@pytest.mark.django_db
def test_post_inverted_period_returns_400_with_field_error(
    staff_client, make_event, staff_event_payload
):
    staff, client = staff_client()
    event = make_event(title="변경 전", official_url="https://example.com/period-edit")

    resp = client.post(
        _edit_url(event),
        staff_event_payload(
            title="수정된 제목",
            official_url="https://example.com/period-edit",
            start_date="2026-09-10",
            end_date="2026-09-01",
        ),
    )

    assert resp.status_code == 400
    event.refresh_from_db()
    assert event.start_date is None
    assert event.end_date is None


@pytest.mark.django_db
def test_post_duplicate_official_url_returns_400_with_field_error(
    staff_client, make_event, staff_event_payload
):
    staff, client = staff_client()
    make_event(title="다른 행사", official_url="https://example.com/taken-by-other")
    event = make_event(title="변경 전", official_url="https://example.com/mine-to-edit")

    resp = client.post(
        _edit_url(event),
        staff_event_payload(title="수정된 제목", official_url="https://example.com/taken-by-other"),
    )

    assert resp.status_code == 400
    assert "공식 URL" in resp.content.decode()
    event.refresh_from_db()
    assert event.official_url == "https://example.com/mine-to-edit"


@pytest.mark.django_db
def test_post_allows_saving_with_unchanged_official_url(
    staff_client, make_event, staff_event_payload
):
    staff, client = staff_client()
    event = make_event(title="변경 전", official_url="https://example.com/unchanged-url")

    resp = client.post(
        _edit_url(event),
        staff_event_payload(title="변경 후", official_url="https://example.com/unchanged-url"),
    )

    assert resp.status_code == 302
    event.refresh_from_db()
    assert event.title == "변경 후"
    assert event.official_url == "https://example.com/unchanged-url"


@pytest.mark.django_db
def test_list_row_links_to_edit_page(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="목록 이벤트", official_url="https://example.com/list-edit-link")

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    assert f"/staff/events/{event.pk}/edit/" in resp.content.decode()


@pytest.mark.django_db
def test_get_form_action_preserves_list_filter_query(staff_client, make_event):
    """폼 action이 화이트리스트 필터 쿼리를 실어야 PRG 후에도 목록 필터가 유지된다.

    회귀 배경: action이 쿼리 없는 URL로 하드코딩돼 POST 시점에 ?warning=이
    유실됐다(뷰의 PRG 보존 코드가 있어도 request.GET이 비어 무효).
    """
    staff, client = staff_client()
    event = make_event(title="필터 보존", official_url="https://example.com/filter-keep")

    resp = client.get(f"{_edit_url(event)}?warning=missing_region")

    assert resp.status_code == 200
    assert (
        f'action="/staff/events/{event.pk}/edit/?warning=missing_region"'
        in resp.content.decode()
    )


@pytest.mark.django_db
def test_post_redirect_preserves_list_filter_query(staff_client, make_event, staff_event_payload):
    staff, client = staff_client()
    event = make_event(title="변경 전", official_url="https://example.com/prg-query")

    resp = client.post(
        f"{_edit_url(event)}?warning=missing_region",
        staff_event_payload(title="변경 후", official_url="https://example.com/prg-query"),
    )

    assert resp.status_code == 302
    assert resp["Location"] == f"{_edit_url(event)}?warning=missing_region"
