"""스태프 이벤트 일괄 비공개 설정 엔드포인트(/staff/events/bulk-unpublish/) 검증.

건별로 성공·실패가 갈려도 응답은 항상 200이며, 요청 구조 오류·상한 초과만 400이다.
"""
import logging

import pytest
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from events.models import Event
from staff.models import StaffActionLog

pytestmark = pytest.mark.web


def bulk_unpublish_url():
    return reverse("staff:event-bulk-unpublish")


@pytest.mark.django_db
def test_익명_사용자는_이벤트_일괄_비공개_설정을_할_수_없다(client):
    response = client.post(
        bulk_unpublish_url(), data={"event_ids": []}, content_type="application/json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_일반_사용자는_이벤트_일괄_비공개_설정을_할_수_없다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.post(
        bulk_unpublish_url(), data={"event_ids": []}, content_type="application/json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [
        {"event_ids": []},
        ["not", "an", "object"],
        {"event_ids": [1, "2"]},
        {"event_ids": [True]},
    ],
    ids=["빈_목록", "리스트가_아닌_본문", "정수가_아닌_원소", "불리언_원소"],
)
def test_요청_구조가_잘못되면_이벤트_일괄_비공개_설정을_거부한다(staff_client, body):
    staff, client = staff_client()

    response = client.post(
        bulk_unpublish_url(), data=body, content_type="application/json"
    )

    assert response.status_code == 400
    assert "event_ids" in response.json()
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_event_ids_개수가_상한을_초과하면_일괄_비공개_설정_요청을_거부하고_아무것도_변경하지_않는다(
    staff_client, make_event
):
    from staff.views import MAX_BULK_EVENT_IDS

    staff, client = staff_client()
    events = [
        make_event(official_url=f"https://example.com/over-cap-{i}")
        for i in range(MAX_BULK_EVENT_IDS + 1)
    ]

    response = client.post(
        bulk_unpublish_url(),
        data={"event_ids": [event.id for event in events]},
        content_type="application/json",
    )

    assert response.status_code == 400
    for event in events:
        event.refresh_from_db()
        assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_게시_중인_이벤트_여러_건을_일괄_비공개로_설정하면_모두_draft가_되고_건별로_감사_로그가_남는다(
    staff_client, make_event
):
    staff, client = staff_client()
    event_a = make_event(official_url="https://example.com/bulk-unpublish-a")
    event_b = make_event(official_url="https://example.com/bulk-unpublish-b")

    response = client.post(
        bulk_unpublish_url(),
        data={"event_ids": [event_a.id, event_b.id]},
        REMOTE_ADDR="203.0.113.5",
        HTTP_USER_AGENT="pytest-agent/1.0",
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {"succeeded": [event_a.id, event_b.id], "failed": []}

    for event in (event_a, event_b):
        event.refresh_from_db()
        assert event.publish_status == Event.PublishStatus.DRAFT

    assert StaffActionLog.objects.count() == 2
    for entry in StaffActionLog.objects.all():
        assert entry.action == StaffActionLog.Action.EVENT_UNPUBLISH
        assert entry.target_event_id in {event_a.id, event_b.id}
        assert entry.actor_id == staff.id
        assert entry.ip_address == "203.0.113.5"
        assert entry.user_agent == "pytest-agent/1.0"


@pytest.mark.django_db
def test_이미_비공개인_이벤트가_섞여도_해당_건은_변경과_로그_없이_성공으로_보고된다(
    staff_client, make_event
):
    staff, client = staff_client()
    published = make_event(official_url="https://example.com/bulk-mixed-published")
    already_draft = make_event(
        official_url="https://example.com/bulk-mixed-draft",
        publish_status="draft",
    )

    response = client.post(
        bulk_unpublish_url(),
        data={"event_ids": [published.id, already_draft.id]},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["succeeded"]) == {published.id, already_draft.id}
    assert body["failed"] == []

    published.refresh_from_db()
    already_draft.refresh_from_db()
    assert published.publish_status == Event.PublishStatus.DRAFT
    assert already_draft.publish_status == Event.PublishStatus.DRAFT

    assert StaffActionLog.objects.count() == 1
    assert StaffActionLog.objects.get().target_event_id == published.id


@pytest.mark.django_db
def test_같은_이벤트_ID_목록으로_두_번_요청해도_두_번째_요청은_상태와_로그를_추가로_바꾸지_않는다(
    staff_client, make_event
):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/bulk-repeat")

    first = client.post(
        bulk_unpublish_url(),
        data={"event_ids": [event.id]},
        content_type="application/json",
    )
    second = client.post(
        bulk_unpublish_url(),
        data={"event_ids": [event.id]},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["succeeded"] == [event.id]
    assert second.json()["succeeded"] == [event.id]
    assert StaffActionLog.objects.count() == 1


@pytest.mark.django_db
def test_존재하지_않는_이벤트_id는_전체_요청을_실패시키지_않고_건별_실패로_보고된다(
    staff_client, make_event
):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/bulk-not-found")

    response = client.post(
        bulk_unpublish_url(),
        data={"event_ids": [999999, event.id]},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "succeeded": [event.id],
        "failed": [{"id": 999999, "reason": "Not found."}],
    }
    assert StaffActionLog.objects.count() == 1


@pytest.mark.django_db
def test_한_항목의_감사_로그_기록이_예기치_못한_오류로_실패해도_나머지_항목_처리는_계속된다(
    staff_client, monkeypatch, caplog, make_event
):
    staff, client = staff_client()
    event_1 = make_event(official_url="https://example.com/bulk-continue-1")
    event_2 = make_event(official_url="https://example.com/bulk-continue-2")
    event_3 = make_event(official_url="https://example.com/bulk-continue-3")

    original_create = StaffActionLog.objects.create

    def flaky_create(*args, target_event=None, **kwargs):
        if target_event is not None and target_event.pk == event_2.pk:
            raise IntegrityError("simulated log write failure")
        return original_create(*args, target_event=target_event, **kwargs)

    monkeypatch.setattr("staff.views.StaffActionLog.objects.create", flaky_create)
    client.raise_request_exception = False

    with caplog.at_level(logging.ERROR, logger="staff.views"):
        response = client.post(
            bulk_unpublish_url(),
            data={"event_ids": [event_1.id, event_2.id, event_3.id]},
            content_type="application/json",
        )

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == [event_1.id, event_3.id]
    assert len(body["failed"]) == 1
    assert body["failed"][0]["id"] == event_2.id
    assert body["failed"][0]["reason"] == "Unexpected error."

    event_1.refresh_from_db()
    event_2.refresh_from_db()
    event_3.refresh_from_db()
    assert event_1.publish_status == Event.PublishStatus.DRAFT
    assert event_2.publish_status == Event.PublishStatus.PUBLISHED
    assert event_3.publish_status == Event.PublishStatus.DRAFT
    assert StaffActionLog.objects.count() == 2

    error_records = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(error_records) == 1
    assert f"event_id={event_2.id}" in error_records[0].message
    assert error_records[0].exc_info is not None


@pytest.mark.django_db
def test_일괄_비공개_설정은_대상_행을_잠그고_읽는다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/bulk-lock")

    with CaptureQueriesContext(connection) as ctx:
        response = client.post(
            bulk_unpublish_url(),
            data={"event_ids": [event.id]},
            content_type="application/json",
        )

    assert response.status_code == 200
    locking_queries = [q for q in ctx.captured_queries if "FOR UPDATE" in q["sql"].upper()]
    assert locking_queries, ctx.captured_queries
