from datetime import date

import pytest

from archive.models import ActivityLogEntry, UserEventStatus
from events.models import Event

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_게시된_행사에_인증된_사용자가_상태를_등록하면_생성된다(client, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id
    assert response.json()["status"] == "planned"


@pytest.mark.django_db
def test_레거시_me_행사상태_경로는_요청하면_404로_비활성_상태를_유지한다(client, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.put(
        f"/api/me/event-statuses/{event.id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_행사_상태_목록을_조회하면_현재_사용자_소유_상태만_반환된다(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    other_user = make_user(email="status-other@example.com", username="status-other")
    owned_event = make_event(title="Owned event", publish_status=Event.PublishStatus.PUBLISHED)
    other_event = make_event(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, owned_event, status="planned")
    make_status(other_user, other_event, status="planned")

    client.force_login(user)
    response = client.get("/api/user-event-statuses/")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"count", "next", "previous", "results"}
    assert payload["count"] == 1
    assert [item["event"] for item in payload["results"]] == [owned_event.id]


@pytest.mark.django_db
def test_행사_상태_목록을_event와_status로_필터링하면_일치하는_항목만_반환된다(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    event_one = make_event(title="Event one", publish_status=Event.PublishStatus.PUBLISHED)
    event_two = make_event(title="Event two", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, event_one, status="planned")
    make_status(user, event_two, status="planned")

    client.force_login(user)
    response = client.get(f"/api/user-event-statuses/?event={event_two.id}&status=planned")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert [item["event"] for item in payload["results"]] == [event_two.id]


@pytest.mark.django_db
def test_행사_상태_목록에_허용되지_않는_status_필터를_지정하면_400으로_거부된다(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    event = make_event(title="Event one", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, event, status="planned")

    client.force_login(user)
    response = client.get("/api/user-event-statuses/?status=attended")

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.django_db
def test_다른_사용자의_행사_상태_상세를_조회하면_404로_숨겨진다(client, make_user, make_event, make_status):
    user = make_user(email="status-owner@example.com", username="status-owner")
    other_user = make_user(email="status-other@example.com", username="status-other")
    event = make_event(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(other_user, event, status="planned")
    status_id = status.id

    client.force_login(other_user)
    own_response = client.get(f"/api/user-event-statuses/{status_id}/")

    assert own_response.status_code == 200

    client.force_login(user)
    response = client.get(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_발행되지_않은_행사에_상태를_등록하면_400으로_거부된다(client, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Draft event", publish_status=Event.PublishStatus.DRAFT)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "event" in response.json()


@pytest.mark.django_db
def test_허용되지_않는_status_값으로_상태를_등록하면_400으로_거부된다(client, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "attended"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "status" in response.json()


@pytest.mark.django_db
def test_이미_존재하는_행사_상태를_다시_등록하면_409_중복_오류가_된다(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    make_status(user, event, status="planned")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "duplicate_user_event_status",
        "detail": "User event status already exists for this event.",
    }


@pytest.mark.django_db
def test_인증된_사용자가_행사_상태를_수정하면_새_상태로_반영된다(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["event"] == event.id
    assert response.json()["status"] == "visited"


@pytest.mark.django_db
def test_지난_행사에서_계획으로_되돌리면_missed_overridden이_고정되어_계획_상태를_유지한다(client, make_user, make_event, make_status):
    """자동 '놓침' 처리된 행을 다시 '계획'으로 되돌릴 때, missed_overridden 플래그가
    없으면 조회 시점에 곧바로 다시 '놓침'으로 파생되어 버린다. 이 PATCH는 그
    플래그를 저장해 사용자의 선택을 유지해야 한다. (같은 시나리오의 파생 상태
    쿼리셋 검증은 test_archive_missed_status.py에 있다.)
    """
    user = make_user(email="revert-user@example.com", username="revert-user")
    event = make_event(
        title="Long-past event",
        publish_status=Event.PublishStatus.PUBLISHED,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),  # 확실히 과거인 날짜
    )
    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 200
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "planned"
    assert row.missed_overridden is True


@pytest.mark.django_db
def test_행사_상태에_PUT_요청을_보내면_405로_거부되고_기존_값이_보존된다(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    other_event = make_event(title="Other event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.put(
        f"/api/user-event-statuses/{status_id}/",
        {"event": other_event.id, "status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 405
    assert client.get(f"/api/user-event-statuses/{status_id}/").json() == {
        "id": status_id,
        "event": event.id,
        "personal_entry": None,
        "status": "planned",
    }


@pytest.mark.django_db
def test_인증된_사용자가_행사_상태를_삭제하면_이후_조회에서_404가_된다(client, make_user, make_event, make_status):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.delete(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 204
    assert client.get(f"/api/user-event-statuses/{status_id}/").status_code == 404


# ---------------------------------------------------------------------------
# CAL-2-13 — DELETE는 remove_user_event_status를 거쳐 status_removed
# ActivityLogEntry가 기록되어야 한다 (perform_destroy 배선 회귀 가드)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_상태_삭제_API를_호출하면_status_removed_활동_이력이_기록된다(
    client, make_user, make_event, make_status
):
    user = make_user(email="status-removed-activity@example.com", username="status-removed-activity")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="planned")
    status_id = status.id

    client.force_login(user)
    response = client.delete(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 204
    assert (
        ActivityLogEntry.objects.filter(
            user=user, kind=ActivityLogEntry.Kind.STATUS_REMOVED, event=event
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_status_필드_없이_PATCH하면_상태_전환_없이_저장된다(client, make_event, make_user):
    user = make_user()
    event = make_event(title="상태 전환")
    status_obj = UserEventStatus.objects.create(
        user=user, event=event, status="planned"
    )

    client.force_login(user)
    # status 필드가 없으면 검증된 status는 None이 되어 전환 없이 그냥 저장만 된다.
    resp = client.patch(
        f"/api/user-event-statuses/{status_obj.id}/",
        data={},
        content_type="application/json",
    )

    assert resp.status_code == 200
    status_obj.refresh_from_db()
    assert status_obj.status == "planned"


@pytest.mark.django_db
def test_interested를_status로_등록하려_하면_400으로_거부된다(client, make_user, make_event):
    """UserEventStatus의 choices에서 'interested'를 제거한 뒤 API도 이를 거부해야 한다."""
    user = make_user(email="status-interested-reject@example.com", username="status-interested-reject")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "interested"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "status" in response.json()


# ---------------------------------------------------------------------------
# §6-b Deferred: status만 바꾸는 PATCH가 마이그레이션 0016이 고친 불일치를
# 재현하면 안 된다 — VisitRecord가 있는 대상은 이 엔드포인트로 계획/놓침으로
# 되돌릴 수 없다 (컬렉션 도메인 설계안 §5 수용 기준 5).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문_기록이_있는_상태에서_계획으로_되돌리려_하면_400으로_거부된다(
    client, make_user, make_event, make_status, make_visit
):
    user = make_user(email="revert-blocked@example.com", username="revert-blocked")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    make_visit(user, event=event, visited_on="2026-07-15")
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "visited"
    assert row.missed_overridden is False


@pytest.mark.django_db
def test_방문_기록이_있는_상태에서_놓침으로_변경하려_하면_400으로_거부된다(
    client, make_user, make_event, make_status, make_visit
):
    user = make_user(email="missed-blocked@example.com", username="missed-blocked")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    make_visit(user, event=event, visited_on="2026-07-15")
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "missed"},
        content_type="application/json",
    )

    assert response.status_code == 400
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "visited"


@pytest.mark.django_db
def test_방문_기록을_삭제한_뒤에는_계획으로_되돌리기가_허용된다(
    client, make_user, make_event, make_status, make_visit
):
    """잘못 기록된 데이터를 복구하는 경로(기록 삭제 후 계획으로 되돌리기)는
    열려 있어야 한다 — 가드는 VisitRecord가 남아 있는 동안만 막는다."""
    user = make_user(email="recovery-path@example.com", username="recovery-path")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    visit = make_visit(user, event=event, visited_on="2026-07-15")
    visit.delete()
    status_id = status.id

    client.force_login(user)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 200
    row = UserEventStatus.objects.get(pk=status_id)
    assert row.status == "planned"


# ---------------------------------------------------------------------------
# 위의 VisitRecord 불변조건은 PATCH 경로만 막았다. DELETE는 가드되지 않아
# (§6-b Deferred, 제품 결정 보류) 새 행을 만들 수 있으므로, DELETE 후 POST가
# 0016이 고친 불일치(`planned`/`missed` 상태와 VisitRecord 공존)를 재현할 수
# 있다. create_user_event_status에도 같은 _has_visit_record 가드가 필요하다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문_기록이_남아있는_상태에서_계획_상태를_새로_생성하려_하면_400으로_거부된다(
    client, make_user, make_event, make_status, make_visit
):
    """삭제 후 재생성 불일치를 재현한다: visited 상태 행을 삭제한 뒤 같은
    대상으로 'planned'를 새로 만들면, VisitRecord가 남아 있으므로 거부되어야 한다."""
    user = make_user(email="create-blocked@example.com", username="create-blocked")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    make_visit(user, event=event, visited_on="2026-07-15")
    status_id = status.id

    client.force_login(user)
    delete_response = client.delete(f"/api/user-event-statuses/{status_id}/")
    assert delete_response.status_code == 204

    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(user=user, event=event).exists()


@pytest.mark.django_db
def test_방문_기록이_남아있는_상태에서_놓침_상태를_새로_생성하려_하면_400으로_거부된다(
    client, make_user, make_event, make_status, make_visit
):
    user = make_user(email="create-missed-blocked@example.com", username="create-missed-blocked")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    status = make_status(user, event, status="visited")
    make_visit(user, event=event, visited_on="2026-07-15")
    status_id = status.id

    client.force_login(user)
    client.delete(f"/api/user-event-statuses/{status_id}/")

    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "missed"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(user=user, event=event).exists()


@pytest.mark.django_db
def test_방문_기록과_일치하는_방문완료_상태를_새로_생성하면_허용된다(client, make_user, make_event, make_visit):
    """기존 VisitRecord와 일치하는 'visited' 신규 생성은 불일치가 아니다 —
    기록과 모순되지 않고 일치하기 때문이다."""
    user = make_user(email="create-visited-ok@example.com", username="create-visited-ok")
    event = make_event(title="Visited event", publish_status=Event.PublishStatus.PUBLISHED)
    make_visit(user, event=event, visited_on="2026-07-15")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "visited"


@pytest.mark.django_db
def test_방문_기록이_없으면_계획_상태_생성이_영향받지_않는다(client, make_user, make_event):
    """회귀 없음 기준선: VisitRecord가 전혀 없을 때 'planned' 생성은 새 가드의
    영향을 받지 않아야 한다."""
    user = make_user(email="create-planned-ok@example.com", username="create-planned-ok")
    event = make_event(title="Fresh event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_개인_장소의_방문_기록이_있는_상태에서_계획_상태를_생성하려_하면_400으로_거부된다(
    client, make_user, make_entry, make_visit
):
    """_has_visit_record는 event와 personal_entry 두 대상 모두를 다룬다 —
    생성 가드도 personal_entry 대상에서 동일하게 거부해야 한다."""
    user = make_user(email="create-entry-blocked@example.com", username="create-entry-blocked")
    entry = make_entry(user, title="개인 장소")
    make_visit(user, personal_entry=entry, visited_on="2026-07-15")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(user=user, personal_entry=entry).exists()


@pytest.mark.django_db
def test_다른_사용자의_방문_기록은_내_계획_상태_생성을_막지_않는다(client, make_user, make_event, make_visit):
    """사용자 간 격리: 같은 행사에 대한 다른 사용자의 VisitRecord가 이 사용자의
    'planned' 신규 생성을 막아서는 안 된다."""
    owner = make_user(email="cross-owner@example.com", username="cross-owner")
    other = make_user(email="cross-other@example.com", username="cross-other")
    event = make_event(title="Shared event", publish_status=Event.PublishStatus.PUBLISHED)
    make_visit(other, event=event, visited_on="2026-07-15")

    client.force_login(owner)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# 생성 스로틀 — 목록에서 여러 행사를 빠르게 연달아 등록할 수 있어 분당 60건.
# GET(목록)은 스로틀 대상이 아님을 함께 확인한다.
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.django_db
def test_상태_생성_요청이_설정된_한도를_초과하면_429로_제한된다(client, make_user, make_event):
    user = make_user(email="status-create-flood@example.com", username="status-create-flood")
    client.force_login(user)

    # 분당 60건 한도: 서로 다른 행사 60개로 채우고 61번째를 확인한다.
    for i in range(60):
        event = make_event(title=f"한도 확인 행사 {i}")
        response = client.post(
            "/api/user-event-statuses/",
            {"event": event.id, "status": "planned"},
            content_type="application/json",
        )
        assert response.status_code == 201, f"create {i} should succeed"

    over_limit_event = make_event(title="한도 초과 행사")
    throttled = client.post(
        "/api/user-event-statuses/",
        {"event": over_limit_event.id, "status": "planned"},
        content_type="application/json",
    )

    assert throttled.status_code == 429
    assert UserEventStatus.objects.count() == 60

    listed = client.get("/api/user-event-statuses/")
    assert listed.status_code == 200
