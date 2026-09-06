"""트랙 20 — 드래프트 admin API의 감사 로그 기록 계약(S1~S3·S6·S7·S11).

이동한 원본 API 동작 검증은 tests/staff/test_staff_draft_api.py가 그대로
맡고, 이 파일은 감사 로그 기록·롤백·트랜잭션 경계만 다룬다. 1차(이동만)
단계에서는 생성·수정 뷰가 아직 StaffActionLog를 남기지 않으므로 S1·S2·S3·
S6·S7은 Red가 정상이고, S11만 이미 Green이다(외부 atomic이 아직 없다는
사실 자체가 SEC-AC1을 만족시키는 가드).
"""
import pytest
from django.db import IntegrityError, connection
from django.test import override_settings

from drafts.models import EventDraft
from staff.models import StaffActionLog

pytestmark = pytest.mark.web


def event_drafts_url():
    from django.urls import reverse

    return reverse("event-drafts")


def event_draft_detail_url(draft_id):
    from django.urls import reverse

    return reverse("event-draft-detail", kwargs={"pk": draft_id})


def _stub_successful_fetch(monkeypatch):
    """생성 성공 몽키패치 선례(tests/staff/test_staff_draft_api.py)를 복제한다."""
    monkeypatch.setattr(
        "drafts.services.fetch_html",
        lambda url: "<html><title>Sample Event</title></html>",
    )
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {
            "raw_title": "Sample Event",
            "raw_text": "Short summary",
            "extracted_title": "Sample Event",
        },
    )


@pytest.mark.django_db
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_관리자가_url로_드래프트_생성에_성공하면_draft_create_감사_로그가_한_건_남는다(
    admin_client, admin_user, monkeypatch
):
    _stub_successful_fetch(monkeypatch)

    response = admin_client.post(
        event_drafts_url(), {"source_url": "https://example.com/audit-create"}
    )

    assert response.status_code == 201
    assert StaffActionLog.objects.count() == 1
    log = StaffActionLog.objects.get()
    assert log.action == StaffActionLog.Action.DRAFT_CREATE
    assert log.target_draft_id == response.json()["id"]
    assert log.actor_id == admin_user.id


@pytest.mark.django_db
def test_관리자가_검토_대기중인_드래프트를_patch로_수정하면_draft_update_감사_로그가_한_건_남는다(
    admin_client, admin_user, make_draft
):
    draft = make_draft("https://example.com/audit-update")

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Updated title"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert StaffActionLog.objects.count() == 1
    log = StaffActionLog.objects.get()
    assert log.action == StaffActionLog.Action.DRAFT_UPDATE
    assert log.target_draft_id == draft.id
    assert log.actor_id == admin_user.id


@pytest.mark.django_db
def test_같은_드래프트를_두_번_patch로_수정하면_draft_update_로그가_두_건_남는다(
    admin_client, make_draft
):
    draft = make_draft("https://example.com/audit-update-twice")

    first = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "First title"},
        content_type="application/json",
    )
    second = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_region": "seoul"},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        StaffActionLog.objects.filter(
            action=StaffActionLog.Action.DRAFT_UPDATE, target_draft=draft
        ).count()
        == 2
    )


@pytest.mark.django_db
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_생성_성공_후_감사_로그_기록이_실패하면_드래프트_생성이_통째로_롤백된다(
    admin_client, monkeypatch
):
    _stub_successful_fetch(monkeypatch)

    def fail_log_create(*args, **kwargs):
        raise IntegrityError("simulated log write failure")

    monkeypatch.setattr("staff.models.StaffActionLog.objects.create", fail_log_create)
    admin_client.raise_request_exception = False

    response = admin_client.post(
        event_drafts_url(), {"source_url": "https://example.com/rollback-create"}
    )

    assert response.status_code == 500
    assert not EventDraft.objects.filter(source_url="https://example.com/rollback-create").exists()
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_patch_성공_후_감사_로그_기록이_실패하면_드래프트_수정이_통째로_롤백된다(
    admin_client, make_draft, monkeypatch
):
    draft = make_draft("https://example.com/rollback-update", extracted_title="Original title")

    def fail_log_create(*args, **kwargs):
        raise IntegrityError("simulated log write failure")

    monkeypatch.setattr("staff.models.StaffActionLog.objects.create", fail_log_create)
    admin_client.raise_request_exception = False

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 500
    draft.refresh_from_db()
    assert draft.extracted_title == "Original title"
    assert StaffActionLog.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db(transaction=True)
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_드래프트_생성의_원본_fetch는_db_트랜잭션_밖에서_실행된다(admin_client, monkeypatch):
    in_atomic_block_calls = []

    def fake_fetch(url):
        in_atomic_block_calls.append(connection.in_atomic_block)
        return "<html><title>Sample Event</title></html>"

    monkeypatch.setattr("drafts.services.fetch_html", fake_fetch)
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Sample Event", "raw_text": "Short summary"},
    )

    response = admin_client.post(
        event_drafts_url(), {"source_url": "https://example.com/atomic-check"}
    )

    assert response.status_code == 201
    assert in_atomic_block_calls == [False]
