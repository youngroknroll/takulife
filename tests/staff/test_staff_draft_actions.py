"""Draft approve/reject action endpoints, relocated to the staff app.

PR-2 sub-step D: same request/response contract as the removed
`drafts.views.AdminEventDraftApproveView`/`RejectView`, but the view boundary
now writes a `StaffActionLog` audit row inside an OUTER `transaction.atomic()`
that wraps the service call's own (inner) atomic block.

PR-D2 item 11: draft.js now posts an optional `rejection_reason` field
alongside a reject request. The empty-body case (Case 5 below) still asserts
the stored value defaults to "" — that contract must not change.
"""
import pytest
from django.db import IntegrityError
from django.urls import reverse

from drafts.models import EventDraft
from events.models import Event
from staff.models import StaffActionLog


def draft_approve_url(draft_id):
    return reverse("staff:draft-approve", kwargs={"draft_id": draft_id})


def draft_reject_url(draft_id):
    return reverse("staff:draft-reject", kwargs={"draft_id": draft_id})


# ---------------------------------------------------------------------------
# Cases 1-3: auth
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_staff_can_approve_pending_draft(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        extracted_title="Sample pending event",
    )

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_cannot_approve_draft(client):
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 403


@pytest.mark.django_db
def test_non_staff_cannot_approve_draft(client, make_user):
    user = make_user()
    client.force_login(user)
    draft = EventDraft.objects.create(source_url="https://example.com/event")

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Case 4: happy approve — review fields, published Event, exactly one log row
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_approve_publishes_event_and_writes_one_audit_log(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        source_name="Official",
        extracted_title="Popup event",
        extracted_category="popup_store",
        extracted_work_title="Oshi Work",
        extracted_location_name="Seoul Mall",
        extracted_region="seoul",
        extracted_start_date="2026-06-01",
        extracted_end_date="2026-06-10",
        extracted_summary="Limited popup",
    )

    response = client.post(
        draft_approve_url(draft.id),
        REMOTE_ADDR="203.0.113.5",
        HTTP_USER_AGENT="pytest-agent/1.0",
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == draft.id
    assert response_data["source_url"] == "https://example.com/event"
    assert response_data["source_name"] == "Official"
    assert response_data["extracted_title"] == "Popup event"
    assert response_data["extracted_category"] == "popup_store"
    assert response_data["extracted_work_title"] == "Oshi Work"
    assert response_data["extracted_location_name"] == "Seoul Mall"
    assert response_data["extracted_region"] == "seoul"
    assert response_data["extracted_start_date"] == "2026-06-01"
    assert response_data["extracted_end_date"] == "2026-06-10"
    assert response_data["extracted_summary"] == "Limited popup"
    assert response_data["review_status"] == EventDraft.ReviewStatus.APPROVED
    assert "event_id" in response_data

    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    assert draft.reviewed_by_id == staff.id
    assert draft.approved_at is not None

    event = Event.objects.get(official_url="https://example.com/event")
    assert response_data["event_id"] == event.id
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.title == "Popup event"
    assert event.category == "popup_store"

    assert StaffActionLog.objects.count() == 1
    entry = StaffActionLog.objects.get()
    assert entry.actor_id == staff.id
    assert entry.action == StaffActionLog.Action.APPROVE
    assert entry.target_draft_id == draft.id
    assert entry.ip_address == "203.0.113.5"
    assert entry.user_agent == "pytest-agent/1.0"


# ---------------------------------------------------------------------------
# Case 5: happy reject
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_reject_marks_draft_rejected_and_writes_one_audit_log(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/rejected-event",
        extracted_title="Rejected event",
    )

    response = client.post(
        draft_reject_url(draft.id),
        REMOTE_ADDR="198.51.100.9",
        HTTP_USER_AGENT="pytest-agent/2.0",
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == draft.id
    assert response_data["source_url"] == "https://example.com/rejected-event"
    assert response_data["extracted_title"] == "Rejected event"
    assert response_data["review_status"] == EventDraft.ReviewStatus.REJECTED
    assert "event_id" not in response_data

    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert draft.reviewed_by_id == staff.id
    assert draft.rejection_reason == ""
    assert not Event.objects.filter(official_url="https://example.com/rejected-event").exists()

    assert StaffActionLog.objects.count() == 1
    entry = StaffActionLog.objects.get()
    assert entry.actor_id == staff.id
    assert entry.action == StaffActionLog.Action.REJECT
    assert entry.target_draft_id == draft.id
    assert entry.ip_address == "198.51.100.9"
    assert entry.user_agent == "pytest-agent/2.0"


@pytest.mark.django_db
def test_reject_stores_populated_rejection_reason(staff_client):
    """PR-D2 item 11: a non-empty rejection_reason in the request body is
    passed through to reject_draft and stored on the draft."""
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/rejected-with-reason",
        extracted_title="Rejected with reason",
    )

    response = client.post(
        draft_reject_url(draft.id),
        {"rejection_reason": "공식 URL이 만료됨"},
        content_type="application/json",
    )

    assert response.status_code == 200
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert draft.rejection_reason == "공식 URL이 만료됨"


# ---------------------------------------------------------------------------
# Case 6: v1 "logs success only" — every non-pending / not-found / publish-
# failure path leaves review fields untouched and writes zero log rows.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_approve_rejects_duplicate_official_url_and_logs_nothing(staff_client):
    staff, client = staff_client()
    Event.objects.create(
        title="Already published",
        official_url="https://example.com/event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        extracted_title="Duplicate event",
    )

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.reviewed_by_id is None
    assert draft.approved_at is None
    assert Event.objects.filter(official_url="https://example.com/event").count() == 1
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_approve_rejects_missing_official_url_and_logs_nothing(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="",
        extracted_title="No URL event",
    )

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"official_url": ["Official URL is required for publication."]}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.reviewed_by_id is None
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_approved_draft_cannot_be_rejected_and_logs_nothing(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    response = client.post(draft_reject_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"detail": "Only pending drafts can be rejected."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    assert draft.rejected_at is None
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_rejected_draft_cannot_be_approved_and_logs_nothing(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.REJECTED,
    )

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"detail": "Only pending drafts can be approved."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert draft.approved_at is None
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_approved_draft_cannot_be_approved_again_and_logs_nothing(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"detail": "Only pending drafts can be approved."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_rejected_draft_cannot_be_rejected_again_and_logs_nothing(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        review_status=EventDraft.ReviewStatus.REJECTED,
    )

    response = client.post(draft_reject_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"detail": "Only pending drafts can be rejected."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_missing_draft_cannot_be_approved_and_logs_nothing(staff_client):
    staff, client = staff_client()

    response = client.post(draft_approve_url(999999))

    assert response.status_code == 404
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_missing_draft_cannot_be_rejected_and_logs_nothing(staff_client):
    staff, client = staff_client()

    response = client.post(draft_reject_url(999999))

    assert response.status_code == 404
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_approve_rejects_blank_title_and_logs_nothing(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/blank-title-draft",
    )

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"title": ["제목을 입력해야 게시할 수 있습니다."]}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.reviewed_by_id is None
    assert draft.approved_at is None
    assert not Event.objects.filter(official_url="https://example.com/blank-title-draft").exists()
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_approve_rejects_title_equal_to_official_url_and_logs_nothing(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/self-titled-draft",
        extracted_title="https://example.com/self-titled-draft",
    )

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 400
    assert response.json() == {"title": ["제목을 입력해야 게시할 수 있습니다."]}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.reviewed_by_id is None
    assert draft.approved_at is None
    assert not Event.objects.filter(official_url="https://example.com/self-titled-draft").exists()
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_approve_returns_controlled_error_when_event_creation_fails_and_logs_nothing(staff_client, monkeypatch):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/event",
        extracted_title="Broken event",
    )

    def fail_create(*args, **kwargs):
        raise ValueError("event create failed")

    monkeypatch.setattr(Event.objects, "create", fail_create)
    client.raise_request_exception = False

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 503
    assert response.json() == {"detail": "Event publication failed."}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.approved_at is None
    assert StaffActionLog.objects.count() == 0


# ---------------------------------------------------------------------------
# Case 7: the outer transaction.atomic() rolls back the whole approval
# (service call + log write) when the audit log write itself fails.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_approve_rolls_back_entirely_when_audit_log_write_fails(staff_client, monkeypatch):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/rollback-event",
        extracted_title="Rollback event",
    )

    def fail_log_create(*args, **kwargs):
        raise IntegrityError("simulated log write failure")

    monkeypatch.setattr("staff.views.StaffActionLog.objects.create", fail_log_create)
    client.raise_request_exception = False

    response = client.post(draft_approve_url(draft.id))

    assert response.status_code == 500
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.reviewed_by_id is None
    assert draft.approved_at is None
    assert not Event.objects.filter(official_url="https://example.com/rollback-event").exists()
    assert StaffActionLog.objects.count() == 0


# ---------------------------------------------------------------------------
# Old /api/event-drafts/<id>/approve|reject/ routes are gone — no redirect.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_old_draft_approve_reject_routes_are_not_supported(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(source_url="https://example.com/legacy-route")

    approve_response = client.post(f"/api/event-drafts/{draft.id}/approve/")
    reject_response = client.post(f"/api/event-drafts/{draft.id}/reject/")

    assert approve_response.status_code == 404
    assert reject_response.status_code == 404
