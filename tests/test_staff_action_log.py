"""StaffActionLog (staff-owned audit model) — PR-2 sub-step C.

Append-only audit trail for draft approve/reject actions. Read access is
restricted to superusers via the Django admin; staff (is_staff, non-super)
must not be able to view or manage log entries there.
"""
import pytest
from django.contrib import admin
from django.test import RequestFactory

from drafts.models import EventDraft
from staff.admin import StaffActionLogAdmin
from staff.models import StaffActionLog


@pytest.mark.django_db
def test_staff_action_log_records_actor_action_target_and_metadata(make_user):
    actor = make_user(is_staff=True)
    draft = EventDraft.objects.create(source_url="https://example.com/logged-event")

    entry = StaffActionLog.objects.create(
        actor=actor,
        action="approve",
        target_draft=draft,
        ip_address="127.0.0.1",
        user_agent="pytest-agent",
    )

    entry.refresh_from_db()
    assert entry.actor_id == actor.id
    assert entry.action == "approve"
    assert entry.target_draft_id == draft.id
    assert entry.ip_address == "127.0.0.1"
    assert entry.user_agent == "pytest-agent"
    assert entry.created_at is not None


@pytest.mark.django_db
def test_staff_action_log_survives_actor_deletion(make_user):
    actor = make_user(is_staff=True)
    entry = StaffActionLog.objects.create(actor=actor, action="reject")

    actor.delete()
    entry.refresh_from_db()

    assert entry.actor_id is None


@pytest.mark.django_db
def test_staff_action_log_survives_target_draft_deletion():
    draft = EventDraft.objects.create(source_url="https://example.com/deleted-draft-log")
    entry = StaffActionLog.objects.create(action="approve", target_draft=draft)

    draft.delete()
    entry.refresh_from_db()

    assert entry.target_draft_id is None


@pytest.mark.django_db
def test_staff_action_log_orders_newest_first(make_user):
    actor = make_user(is_staff=True)
    first = StaffActionLog.objects.create(actor=actor, action="approve")
    second = StaffActionLog.objects.create(actor=actor, action="reject")

    entries = list(StaffActionLog.objects.all())

    assert entries == [second, first]


@pytest.mark.django_db
def test_staff_action_log_str_without_target_draft_omits_hash_none(make_user):
    actor = make_user(is_staff=True)
    entry = StaffActionLog.objects.create(
        actor=actor, action=StaffActionLog.Action.HOME_CATEGORIES, target_draft=None
    )

    text = str(entry)

    assert "#None" not in text
    assert text == f"home_categories by {actor.id}"


@pytest.mark.django_db
def test_staff_action_log_admin_view_permission_denied_for_plain_staff(make_user):
    staff_user = make_user(is_staff=True)
    request = RequestFactory().get("/admin/staff/staffactionlog/")
    request.user = staff_user
    log_admin = StaffActionLogAdmin(StaffActionLog, admin.site)

    assert log_admin.has_view_permission(request) is False
    assert log_admin.has_module_permission(request) is False


@pytest.mark.django_db
def test_staff_action_log_admin_view_permission_granted_for_superuser(make_user):
    superuser = make_user(is_staff=True, is_superuser=True)
    request = RequestFactory().get("/admin/staff/staffactionlog/")
    request.user = superuser
    log_admin = StaffActionLogAdmin(StaffActionLog, admin.site)

    assert log_admin.has_view_permission(request) is True
    assert log_admin.has_module_permission(request) is True


@pytest.mark.django_db
def test_staff_action_log_admin_disallows_add_change_delete(make_user):
    staff_user = make_user(is_staff=True, is_superuser=True)
    request = RequestFactory().get("/admin/staff/staffactionlog/")
    request.user = staff_user
    log_admin = StaffActionLogAdmin(StaffActionLog, admin.site)

    assert log_admin.has_add_permission(request) is False
    assert log_admin.has_change_permission(request) is False
    assert log_admin.has_delete_permission(request) is False
