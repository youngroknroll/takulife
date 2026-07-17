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

pytestmark = pytest.mark.web


def bulk_approve_url():
    return reverse("staff:draft-bulk-approve")


# ---------------------------------------------------------------------------
# Cases 1-2: auth
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_익명_사용자는_드래프트_일괄_승인을_할_수_없다(client):
    response = client.post(
        bulk_approve_url(), data={"draft_ids": []}, content_type="application/json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_일반_사용자는_드래프트_일괄_승인을_할_수_없다(client, make_user):
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
def test_draft_ids가_비어있으면_일괄_승인_요청을_거부한다(staff_client):
    staff, client = staff_client()

    response = client.post(
        bulk_approve_url(), data={"draft_ids": []}, content_type="application/json"
    )

    assert response.status_code == 400
    assert response.json() == {"draft_ids": ["draft_ids must be a non-empty list."]}
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_요청_본문이_객체가_아니면_일괄_승인_요청을_거부한다(staff_client):
    staff, client = staff_client()

    response = client.post(bulk_approve_url(), [1, 2, 3], content_type="application/json")

    assert response.status_code == 400
    assert response.json() == {"draft_ids": ["draft_ids must be a non-empty list."]}
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_draft_ids에_정수가_아닌_값이_있으면_일괄_승인_요청을_거부한다(staff_client):
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
def test_draft_ids_개수가_상한을_초과하면_일괄_승인_요청을_거부하고_아무것도_변경하지_않는다(staff_client, make_draft):
    staff, client = staff_client()
    drafts = [
        make_draft(f"https://example.com/over-cap-{i}", extracted_title=f"Over cap {i}")
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
def test_draft_ids에_불리언_값이_섞이면_정수가_아닌_값으로_거부한다(staff_client):
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
def test_draft_ids가_리스트가_아니면_일괄_승인_요청을_거부한다(staff_client):
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
def test_대기중_드래프트_여러_건을_일괄_승인하면_모두_게시되고_건별로_감사_로그가_남는다(staff_client, make_draft):
    staff, client = staff_client()
    draft_a = make_draft("https://example.com/bulk-a", extracted_title="Bulk A")
    draft_b = make_draft("https://example.com/bulk-b", extracted_title="Bulk B")

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
def test_draft_ids_개수가_정확히_상한이면_전부_승인된다(staff_client, make_draft):
    """Boundary lock-in: exactly MAX_BULK_APPROVE_DRAFT_IDS pending drafts must
    pass the cap check and all succeed (over-cap is tested separately)."""
    staff, client = staff_client()
    drafts = [
        make_draft(f"https://example.com/at-cap-{i}", extracted_title=f"At cap {i}")
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
def test_존재하지_않는_draft_id는_전체_요청_실패가_아니라_건별_실패로_보고된다(staff_client):
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
def test_같은_draft_id를_중복_전달하면_첫_처리만_성공하고_두번째는_이미_처리됨으로_실패한다(staff_client, make_draft):
    staff, client = staff_client()
    draft = make_draft("https://example.com/bulk-repeat", extracted_title="Bulk repeat")

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
def test_여러_실패_사유가_섞인_draft_ids를_일괄_승인하면_성공과_실패가_사유와_함께_부분_보고된다(staff_client, make_draft):
    staff, client = staff_client()

    already_approved = make_draft("https://example.com/bulk-already-approved", extracted_title="Already approved", review_status=EventDraft.ReviewStatus.APPROVED)
    ok_1 = make_draft("https://example.com/bulk-ok-1", extracted_title="Bulk ok 1")
    Event.objects.create(
        title="Already published",
        official_url="https://example.com/bulk-duplicate",
        publish_status=Event.PublishStatus.PUBLISHED,
    )
    duplicate_url = make_draft("https://example.com/bulk-duplicate", extracted_title="Duplicate url draft")
    blank_title = make_draft("https://example.com/bulk-blank-title")
    ok_2 = make_draft("https://example.com/bulk-ok-2", extracted_title="Bulk ok 2")

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
def test_한_항목의_감사_로그_기록이_예기치_못한_오류로_실패해도_나머지_항목_처리는_계속된다(staff_client, monkeypatch, caplog, make_draft):
    staff, client = staff_client()
    draft_1 = make_draft("https://example.com/bulk-continue-1", extracted_title="Bulk continue 1")
    draft_2 = make_draft("https://example.com/bulk-continue-2", extracted_title="Bulk continue 2")
    draft_3 = make_draft("https://example.com/bulk-continue-3", extracted_title="Bulk continue 3")

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
