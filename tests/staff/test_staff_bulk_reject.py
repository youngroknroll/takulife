"""드래프트 일괄 반려 엔드포인트(/staff/drafts/bulk-reject/) 검증(B3).

구조 검증·상한·부분 실패 보고 정책은 StaffDraftBulkApproveView와 같다
(test_staff_bulk_approve.py 참고) — 여기서는 반려 고유 동작(사유 저장,
REJECT 로그)만 다룬다.
"""
import pytest
from django.urls import reverse

from drafts.models import EventDraft
from staff.models import StaffActionLog
from staff.views import MAX_BULK_APPROVE_DRAFT_IDS

pytestmark = pytest.mark.web


def bulk_reject_url():
    return reverse("staff:draft-bulk-reject")


@pytest.mark.django_db
def test_익명_사용자는_드래프트_일괄_반려를_할_수_없다(client):
    response = client.post(
        bulk_reject_url(), data={"draft_ids": []}, content_type="application/json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_일반_사용자는_드래프트_일괄_반려를_할_수_없다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.post(
        bulk_reject_url(), data={"draft_ids": []}, content_type="application/json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_draft_ids가_비어있으면_일괄_반려_요청을_거부한다(staff_client):
    staff, client = staff_client()

    response = client.post(
        bulk_reject_url(), data={"draft_ids": []}, content_type="application/json"
    )

    assert response.status_code == 400
    assert response.json() == {"draft_ids": ["draft_ids must be a non-empty list."]}
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_draft_ids_개수가_상한을_초과하면_일괄_반려_요청을_거부하고_아무것도_변경하지_않는다(staff_client, make_draft):
    staff, client = staff_client()
    drafts = [
        make_draft(f"https://example.com/reject-over-cap-{i}")
        for i in range(MAX_BULK_APPROVE_DRAFT_IDS + 1)
    ]

    response = client.post(
        bulk_reject_url(),
        data={"draft_ids": [draft.id for draft in drafts]},
        content_type="application/json",
    )

    assert response.status_code == 400
    for draft in drafts:
        draft.refresh_from_db()
        assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_대기중_드래프트_여러_건을_일괄_반려하면_모두_반려되고_건별로_감사_로그가_남는다(staff_client, make_draft):
    staff, client = staff_client()
    draft_a = make_draft("https://example.com/bulk-reject-a")
    draft_b = make_draft("https://example.com/bulk-reject-b")

    response = client.post(
        bulk_reject_url(),
        data={"draft_ids": [draft_a.id, draft_b.id]},
        REMOTE_ADDR="203.0.113.9",
        HTTP_USER_AGENT="pytest-agent/4.0",
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"succeeded": [draft_a.id, draft_b.id], "failed": []}

    for draft in (draft_a, draft_b):
        draft.refresh_from_db()
        assert draft.review_status == EventDraft.ReviewStatus.REJECTED
        assert draft.reviewed_by_id == staff.id
        assert draft.rejected_at is not None

    assert StaffActionLog.objects.count() == 2
    for entry in StaffActionLog.objects.all():
        assert entry.actor_id == staff.id
        assert entry.action == StaffActionLog.Action.REJECT
        assert entry.target_draft_id in {draft_a.id, draft_b.id}
        assert entry.ip_address == "203.0.113.9"
        assert entry.user_agent == "pytest-agent/4.0"


@pytest.mark.django_db
def test_반려_사유를_함께_보내면_대상_전원에게_같은_사유가_저장된다(staff_client, make_draft):
    staff, client = staff_client()
    draft_a = make_draft("https://example.com/bulk-reject-reason-a")
    draft_b = make_draft("https://example.com/bulk-reject-reason-b")

    response = client.post(
        bulk_reject_url(),
        data={
            "draft_ids": [draft_a.id, draft_b.id],
            "rejection_reason": "출처 신뢰도 낮음",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    for draft in (draft_a, draft_b):
        draft.refresh_from_db()
        assert draft.rejection_reason == "출처 신뢰도 낮음"


@pytest.mark.django_db
def test_존재하지_않는_draft_id는_전체_요청_실패가_아니라_건별_실패로_보고된다(staff_client):
    staff, client = staff_client()

    response = client.post(
        bulk_reject_url(),
        data={"draft_ids": [999999]},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "succeeded": [],
        "failed": [{"id": 999999, "reason": "Not found."}],
    }
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_이미_승인된_드래프트가_섞여도_나머지는_반려되고_해당_건만_실패로_보고된다(staff_client, make_draft):
    staff, client = staff_client()
    already_approved = make_draft(
        "https://example.com/bulk-reject-already-approved",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )
    ok = make_draft("https://example.com/bulk-reject-ok")

    response = client.post(
        bulk_reject_url(),
        data={"draft_ids": [already_approved.id, ok.id]},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "succeeded": [ok.id],
        "failed": [
            {
                "id": already_approved.id,
                "reason": "Only pending drafts can be rejected.",
            }
        ],
    }
    ok.refresh_from_db()
    assert ok.review_status == EventDraft.ReviewStatus.REJECTED
    assert StaffActionLog.objects.count() == 1
