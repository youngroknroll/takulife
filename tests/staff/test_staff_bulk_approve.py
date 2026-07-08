"""Bulk-approve endpoint for staff: /staff/drafts/bulk-approve/.

Per-item independent outer-atomic (approve_draft + StaffActionLog), same
semantics as StaffDraftApproveView repeated per id. Partial success is
normal — the response is always 200 with {"succeeded": [...], "failed":
[{"id", "reason"}]}. A 400 is reserved for structural request errors caught
before the loop starts (empty/non-integer/over-cap draft_ids).
"""
import logging

import pytest
from django.db import IntegrityError
from django.urls import reverse

from drafts.models import EventDraft
from events.models import Event
from staff.models import StaffActionLog
from staff.views import MAX_BULK_APPROVE_DRAFT_IDS


def bulk_approve_url():
    return reverse("staff:draft-bulk-approve")


# ---------------------------------------------------------------------------
# Cases 1-2: auth
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_anonymous_cannot_bulk_approve_drafts(client):
    response = client.post(
        bulk_approve_url(), data={"draft_ids": []}, content_type="application/json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_non_staff_cannot_bulk_approve_drafts(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.post(
        bulk_approve_url(), data={"draft_ids": []}, content_type="application/json"
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Cases 3-5: structural validation (400, before the loop starts)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_approve_rejects_empty_draft_ids(staff_client):
    staff, client = staff_client()

    response = client.post(
        bulk_approve_url(), data={"draft_ids": []}, content_type="application/json"
    )

    assert response.status_code == 400
    assert response.json() == {"draft_ids": ["draft_ids must be a non-empty list."]}
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_bulk_approve_rejects_non_dict_body(staff_client):
    staff, client = staff_client()

    response = client.post(bulk_approve_url(), [1, 2, 3], content_type="application/json")

    assert response.status_code == 400
    assert response.json() == {"draft_ids": ["draft_ids must be a non-empty list."]}
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_bulk_approve_rejects_non_integer_draft_id(staff_client):
    staff, client = staff_client()

    response = client.post(
        bulk_approve_url(),
        data={"draft_ids": [1, "abc"]},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"draft_ids": ["draft_ids must contain only integers."]}
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_bulk_approve_rejects_when_exceeding_max_draft_ids(staff_client):
    staff, client = staff_client()
    drafts = [
        EventDraft.objects.create(
            source_url=f"https://example.com/over-cap-{i}",
            extracted_title=f"Over cap {i}",
        )
        for i in range(MAX_BULK_APPROVE_DRAFT_IDS + 1)
    ]

    response = client.post(
        bulk_approve_url(),
        data={"draft_ids": [draft.id for draft in drafts]},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "draft_ids": [
            f"draft_ids must contain at most {MAX_BULK_APPROVE_DRAFT_IDS} ids."
        ]
    }
    for draft in drafts:
        draft.refresh_from_db()
        assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_bulk_approve_rejects_boolean_as_draft_id(staff_client):
    """Regression guard: bool is an int subclass in Python — must not sneak past
    the integer check (True/False are not valid draft ids)."""
    staff, client = staff_client()

    response = client.post(
        bulk_approve_url(),
        data={"draft_ids": [1, True]},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"draft_ids": ["draft_ids must contain only integers."]}
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_bulk_approve_rejects_non_list_draft_ids(staff_client):
    """Regression guard: a non-list draft_ids value (e.g. a bare string) must be
    rejected structurally rather than iterated."""
    staff, client = staff_client()

    response = client.post(
        bulk_approve_url(),
        data={"draft_ids": "abc"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"draft_ids": ["draft_ids must be a non-empty list."]}
    assert StaffActionLog.objects.count() == 0


# ---------------------------------------------------------------------------
# Case 6: happy path — 2 pending drafts, both approved, one log row each
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_approve_approves_all_pending_drafts_and_logs_each_success(staff_client):
    staff, client = staff_client()
    draft_a = EventDraft.objects.create(
        source_url="https://example.com/bulk-a",
        extracted_title="Bulk A",
    )
    draft_b = EventDraft.objects.create(
        source_url="https://example.com/bulk-b",
        extracted_title="Bulk B",
    )

    response = client.post(
        bulk_approve_url(),
        data={"draft_ids": [draft_a.id, draft_b.id]},
        REMOTE_ADDR="203.0.113.7",
        HTTP_USER_AGENT="pytest-agent/3.0",
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"succeeded": [draft_a.id, draft_b.id], "failed": []}

    for draft, source_url in ((draft_a, "https://example.com/bulk-a"), (draft_b, "https://example.com/bulk-b")):
        draft.refresh_from_db()
        assert draft.review_status == EventDraft.ReviewStatus.APPROVED
        assert draft.reviewed_by_id == staff.id
        assert draft.approved_at is not None
        assert Event.objects.filter(official_url=source_url, publish_status=Event.PublishStatus.PUBLISHED).exists()

    assert StaffActionLog.objects.count() == 2
    for entry in StaffActionLog.objects.all():
        assert entry.actor_id == staff.id
        assert entry.action == StaffActionLog.Action.APPROVE
        assert entry.target_draft_id in {draft_a.id, draft_b.id}
        assert entry.ip_address == "203.0.113.7"
        assert entry.user_agent == "pytest-agent/3.0"


@pytest.mark.django_db
def test_bulk_approve_approves_exactly_max_draft_ids(staff_client):
    """Boundary lock-in: exactly MAX_BULK_APPROVE_DRAFT_IDS pending drafts must
    pass the cap check and all succeed (over-cap is tested separately)."""
    staff, client = staff_client()
    drafts = [
        EventDraft.objects.create(
            source_url=f"https://example.com/at-cap-{i}",
            extracted_title=f"At cap {i}",
        )
        for i in range(MAX_BULK_APPROVE_DRAFT_IDS)
    ]

    response = client.post(
        bulk_approve_url(),
        data={"draft_ids": [draft.id for draft in drafts]},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "succeeded": [draft.id for draft in drafts],
        "failed": [],
    }
    for draft in drafts:
        draft.refresh_from_db()
        assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    assert StaffActionLog.objects.count() == MAX_BULK_APPROVE_DRAFT_IDS


# ---------------------------------------------------------------------------
# Case 7: unknown draft id is a per-item failure, not a 404
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_approve_reports_not_found_for_unknown_draft_id(staff_client):
    staff, client = staff_client()

    response = client.post(
        bulk_approve_url(),
        data={"draft_ids": [999999]},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "succeeded": [],
        "failed": [{"id": 999999, "reason": "Not found."}],
    }
    assert StaffActionLog.objects.count() == 0


# ---------------------------------------------------------------------------
# Case 8: repeated id — 1st pass succeeds, 2nd pass fails naturally
# (no dedup — this is the documented behavior, not a bug)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_approve_treats_repeated_id_as_success_then_already_processed(staff_client):
    staff, client = staff_client()
    draft = EventDraft.objects.create(
        source_url="https://example.com/bulk-repeat",
        extracted_title="Bulk repeat",
    )

    response = client.post(
        bulk_approve_url(),
        data={"draft_ids": [draft.id, draft.id]},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "succeeded": [draft.id],
        "failed": [{"id": draft.id, "reason": "Only pending drafts can be approved."}],
    }
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    assert StaffActionLog.objects.count() == 1


# ---------------------------------------------------------------------------
# Case 9: mixed results — already-approved, ok, duplicate-url, blank-title, ok
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_approve_mixed_results_partial_success_with_reasons(staff_client):
    staff, client = staff_client()

    already_approved = EventDraft.objects.create(
        source_url="https://example.com/bulk-already-approved",
        extracted_title="Already approved",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )
    ok_1 = EventDraft.objects.create(
        source_url="https://example.com/bulk-ok-1",
        extracted_title="Bulk ok 1",
    )
    Event.objects.create(
        title="Already published",
        official_url="https://example.com/bulk-duplicate",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    duplicate_url = EventDraft.objects.create(
        source_url="https://example.com/bulk-duplicate",
        extracted_title="Duplicate url draft",
    )
    blank_title = EventDraft.objects.create(
        source_url="https://example.com/bulk-blank-title",
    )
    ok_2 = EventDraft.objects.create(
        source_url="https://example.com/bulk-ok-2",
        extracted_title="Bulk ok 2",
    )

    response = client.post(
        bulk_approve_url(),
        data={
            "draft_ids": [
                already_approved.id,
                ok_1.id,
                duplicate_url.id,
                blank_title.id,
                ok_2.id,
            ]
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "succeeded": [ok_1.id, ok_2.id],
        "failed": [
            {"id": already_approved.id, "reason": "Only pending drafts can be approved."},
            {
                "id": duplicate_url.id,
                "reason": "Event with this official URL already exists.",
            },
            {"id": blank_title.id, "reason": "제목을 입력해야 게시할 수 있습니다."},
        ],
    }

    for draft, official_url in (
        (duplicate_url, "https://example.com/bulk-duplicate"),
        (blank_title, "https://example.com/bulk-blank-title"),
    ):
        draft.refresh_from_db()
        assert draft.review_status == EventDraft.ReviewStatus.PENDING

    assert Event.objects.filter(official_url="https://example.com/bulk-ok-1").exists()
    assert Event.objects.filter(official_url="https://example.com/bulk-ok-2").exists()
    assert not Event.objects.filter(official_url="https://example.com/bulk-blank-title").exists()
    assert StaffActionLog.objects.count() == 2


# ---------------------------------------------------------------------------
# Case 10 (must not be skipped): an unclassified exception in one item's
# StaffActionLog write is caught, that item's own outer-atomic block rolls
# back, and the batch continues with the remaining items.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_approve_continues_processing_after_unexpected_error_in_one_item(staff_client, monkeypatch, caplog):
    staff, client = staff_client()
    draft_1 = EventDraft.objects.create(
        source_url="https://example.com/bulk-continue-1",
        extracted_title="Bulk continue 1",
    )
    draft_2 = EventDraft.objects.create(
        source_url="https://example.com/bulk-continue-2",
        extracted_title="Bulk continue 2",
    )
    draft_3 = EventDraft.objects.create(
        source_url="https://example.com/bulk-continue-3",
        extracted_title="Bulk continue 3",
    )

    original_create = StaffActionLog.objects.create

    def flaky_create(*args, target_draft=None, **kwargs):
        if target_draft is not None and target_draft.id == draft_2.id:
            raise IntegrityError("simulated log write failure")
        return original_create(*args, target_draft=target_draft, **kwargs)

    monkeypatch.setattr("staff.views.StaffActionLog.objects.create", flaky_create)
    client.raise_request_exception = False

    with caplog.at_level(logging.ERROR, logger="staff.views"):
        response = client.post(
            bulk_approve_url(),
            data={"draft_ids": [draft_1.id, draft_2.id, draft_3.id]},
            content_type="application/json",
        )

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == [draft_1.id, draft_3.id]
    assert len(body["failed"]) == 1
    assert body["failed"][0]["id"] == draft_2.id
    assert isinstance(body["failed"][0]["reason"], str) and body["failed"][0]["reason"]

    draft_1.refresh_from_db()
    draft_2.refresh_from_db()
    draft_3.refresh_from_db()
    assert draft_1.review_status == EventDraft.ReviewStatus.APPROVED
    assert draft_2.review_status == EventDraft.ReviewStatus.PENDING
    assert draft_3.review_status == EventDraft.ReviewStatus.APPROVED
    assert StaffActionLog.objects.count() == 2

    error_records = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(error_records) == 1
    assert f"draft_id={draft_2.id}" in error_records[0].message
    assert error_records[0].exc_info is not None
