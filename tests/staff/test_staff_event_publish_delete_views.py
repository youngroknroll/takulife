"""staff.views — PR-E3 D (publish-status toggle + guarded hard delete).

Covers /staff/events/<pk>/toggle-publish/ (unpublish<->republish) and
/staff/events/<pk>/delete/ (2-step server-rendered confirm — no new JS file,
see prompt_plan.md's "하지 말 것"). Both are POST-only SSR actions reached
from the edit page's own forms, never a JSON API.
"""
import datetime

import pytest

from archive.models import CollectionItem, EventInterest
from events.models import Event
from staff.models import StaffActionLog


def _toggle_url(event):
    return f"/staff/events/{event.pk}/toggle-publish/"


def _delete_url(event):
    return f"/staff/events/{event.pk}/delete/"


# ---------------------------------------------------------------------------
# toggle-publish
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_toggle_publish_anonymous_redirects_to_login(client, make_event):
    event = make_event(official_url="https://example.com/toggle-anon")

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next=/staff/events/{event.pk}/toggle-publish/"


@pytest.mark.django_db
def test_toggle_publish_non_staff_returns_403(client, make_user, make_event):
    user = make_user()
    client.force_login(user)
    event = make_event(official_url="https://example.com/toggle-403")

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 403


@pytest.mark.django_db
def test_toggle_publish_get_not_allowed(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/toggle-get")

    resp = client.get(_toggle_url(event))

    assert resp.status_code == 405
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.PUBLISHED


@pytest.mark.django_db
def test_toggle_publish_unpublishes_a_published_event(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/toggle-unpublish")

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 302
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT
    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_UNPUBLISH
    assert log.actor_id == staff.id


@pytest.mark.django_db
def test_toggle_publish_republishes_a_draft_event(staff_client, make_draft_event):
    staff, client = staff_client()
    event = make_draft_event(
        title="초안", official_url="https://example.com/toggle-republish"
    )

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 302
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_REPUBLISH


@pytest.mark.django_db
def test_toggle_publish_rejects_republish_of_event_missing_title(staff_client, make_draft_event):
    staff, client = staff_client()
    event = make_draft_event(title="", official_url="https://example.com/toggle-broken")

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 302
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT
    assert not StaffActionLog.objects.filter(target_event=event).exists()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_delete_anonymous_redirects_to_login(client, make_event):
    event = make_event(official_url="https://example.com/delete-anon")

    resp = client.post(_delete_url(event))

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next=/staff/events/{event.pk}/delete/"


@pytest.mark.django_db
def test_delete_non_staff_returns_403(client, make_user, make_event):
    user = make_user()
    client.force_login(user)
    event = make_event(official_url="https://example.com/delete-403")

    resp = client.post(_delete_url(event))

    assert resp.status_code == 403


@pytest.mark.django_db
def test_delete_get_not_allowed(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/delete-get")

    resp = client.get(_delete_url(event))

    assert resp.status_code == 405
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_delete_first_post_shows_confirmation_without_deleting(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="삭제 대상", official_url="https://example.com/delete-confirm-step")

    resp = client.post(_delete_url(event))

    assert resp.status_code == 200
    assert "삭제" in resp.content.decode()
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_delete_confirmed_post_deletes_event_and_writes_audit_log_prg_to_list(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="삭제 대상", official_url="https://example.com/delete-confirmed")

    resp = client.post(_delete_url(event), {"confirmed": "yes"})

    assert resp.status_code == 302
    assert resp.url == "/staff/events/"
    assert not Event.objects.filter(pk=event.pk).exists()
    log = StaffActionLog.objects.get(action=StaffActionLog.Action.EVENT_DELETE)
    assert log.actor_id == staff.id
    assert log.target_event_id is None


@pytest.mark.django_db
def test_delete_preserves_list_filter_query_on_prg(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="삭제 대상", official_url="https://example.com/delete-filter-prg")

    resp = client.post(
        f"{_delete_url(event)}?warning=missing_region", {"confirmed": "yes"}
    )

    assert resp.status_code == 302
    assert resp.url == "/staff/events/?warning=missing_region"


@pytest.mark.django_db
def test_delete_blocked_when_archive_references_exist(staff_client, make_user, make_event):
    staff, client = staff_client()
    event = make_event(title="찜된 행사", official_url="https://example.com/delete-blocked")
    interested_user = make_user()
    EventInterest.objects.create(user=interested_user, event=event)

    resp = client.post(_delete_url(event), {"confirmed": "yes"})

    assert resp.status_code == 302
    assert Event.objects.filter(pk=event.pk).exists()
    assert not StaffActionLog.objects.filter(action=StaffActionLog.Action.EVENT_DELETE).exists()


@pytest.mark.django_db
def test_edit_page_shows_reference_counts_instead_of_delete_button(staff_client, make_user, make_event):
    staff, client = staff_client()
    event = make_event(title="찜된 행사", official_url="https://example.com/edit-blocked-delete")
    interested_user = make_user()
    EventInterest.objects.create(user=interested_user, event=event)

    resp = client.get(f"/staff/events/{event.pk}/edit/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "찜 1" in content
    assert f'action="/staff/events/{event.pk}/delete/"' not in content


@pytest.mark.django_db
def test_edit_page_shows_delete_button_when_unreferenced(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="깨끗한 행사", official_url="https://example.com/edit-allowed-delete")

    resp = client.get(f"/staff/events/{event.pk}/edit/")

    assert resp.status_code == 200
    assert f'action="/staff/events/{event.pk}/delete/"' in resp.content.decode()


@pytest.mark.django_db
def test_edit_page_shows_reference_counts_for_collection_item_reference(
    staff_client, make_user, make_event
):
    staff, client = staff_client()
    event = make_event(
        title="컬렉션 참조 행사", official_url="https://example.com/edit-blocked-collection"
    )
    owner = make_user()
    CollectionItem.objects.create(user=owner, name="참조 굿즈", event=event)

    resp = client.get(f"/staff/events/{event.pk}/edit/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "컬렉션 1" in content
    assert f'action="/staff/events/{event.pk}/delete/"' not in content


@pytest.mark.django_db
def test_delete_blocked_message_includes_collection_item_count(
    staff_client, make_user, make_event
):
    staff, client = staff_client()
    event = make_event(
        title="컬렉션 참조 삭제 차단", official_url="https://example.com/delete-blocked-collection"
    )
    owner = make_user()
    CollectionItem.objects.create(user=owner, name="차단용 굿즈", event=event)

    resp = client.post(_delete_url(event), {"confirmed": "yes"}, follow=True)

    assert Event.objects.filter(pk=event.pk).exists()
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert "컬렉션 1" in messages_text
