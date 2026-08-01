"""EventInterest API 엔드포인트 동작 테스트.

  POST   /api/event-interests/         → 201 또는 409
  GET    /api/event-interests/         → 페이지네이션 목록(사용자 범위 한정)
  GET    /api/event-interests/<id>/    → 200 또는 404
  DELETE /api/event-interests/<id>/    → 204 또는 404
"""

import pytest

from archive.models import ActivityLogEntry, EventInterest

pytestmark = pytest.mark.web


# ---------------------------------------------------------------------------
# 생성 — 201
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_행사_찜을_등록하면_201을_응답한다(client, make_user, make_event):
    user = make_user(username="interest-create-user")
    event = make_event(title="Popup Store A")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["event"] == event.id
    assert "id" in data
    assert EventInterest.objects.filter(user=user, event=event).exists()


# ---------------------------------------------------------------------------
# 생성 — 중복 시 409
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_이미_찜한_행사를_다시_등록하면_409를_응답한다(client, make_user, make_event):
    user = make_user(username="interest-dup-user")
    event = make_event(title="Popup Store B")

    client.force_login(user)
    client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "duplicate_event_interest",
        "detail": "Event interest already exists for this event.",
    }


# ---------------------------------------------------------------------------
# 생성 — 미공개 행사 → 400
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_미공개_행사를_찜하면_400을_응답한다(client, make_user, make_draft_event):
    user = make_user(username="interest-draft-user")
    event = make_draft_event(title="Draft Popup")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "event" in response.json()


# ---------------------------------------------------------------------------
# 목록 — 사용자 범위 한정
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_찜_목록_조회는_본인_소유로만_한정된다(client, make_user, make_event, make_interest):
    user = make_user(username="interest-list-user")
    other = make_user(username="interest-list-other")
    event_a = make_event(title="Event A")
    event_b = make_event(title="Event B")

    make_interest(user, event=event_a)
    make_interest(other, event=event_b)

    client.force_login(user)
    response = client.get("/api/event-interests/")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"count", "next", "previous", "results"}
    assert payload["count"] == 1
    assert payload["results"][0]["event"] == event_a.id


# ---------------------------------------------------------------------------
# 목록 — 최신순 정렬
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_찜_목록은_최신_등록순으로_정렬된다(client, make_user, make_event, make_interest):
    user = make_user(username="interest-order-user")
    event_a = make_event(title="Event Order A")
    event_b = make_event(title="Event Order B")

    first_interest = make_interest(user, event=event_a)
    second_interest = make_interest(user, event=event_b)

    client.force_login(user)
    response = client.get("/api/event-interests/")

    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["id"] == second_interest.id
    assert results[1]["id"] == first_interest.id


# ---------------------------------------------------------------------------
# 삭제 — 204 이후 404
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_찜을_삭제하면_204이고_이후_조회는_404가_된다(client, make_user, make_event):
    user = make_user(username="interest-delete-user")
    event = make_event(title="Popup Delete")

    client.force_login(user)
    create_response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )
    interest_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/event-interests/{interest_id}/")
    assert delete_response.status_code == 204
    assert not EventInterest.objects.filter(pk=interest_id).exists()

    get_response = client.get(f"/api/event-interests/{interest_id}/")
    assert get_response.status_code == 404


# ---------------------------------------------------------------------------
# CAL-2-03 — 삭제는 remove_event_interest를 거쳐야 interest_removed 활동
# 이력이 남는다(perform_destroy 배선 회귀 가드, 이중 달력 Test List §단계 2)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_찜_해제_API를_호출하면_interest_removed_활동_이력이_기록된다(client, make_user, make_event):
    user = make_user(username="interest-removed-activity-user")
    event = make_event(title="Popup Activity Removed")

    client.force_login(user)
    create_response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )
    interest_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/event-interests/{interest_id}/")

    assert delete_response.status_code == 204
    assert (
        ActivityLogEntry.objects.filter(
            user=user, kind=ActivityLogEntry.Kind.INTEREST_REMOVED, event=event
        ).count()
        == 1
    )


# ---------------------------------------------------------------------------
# IDOR — 다른 사용자가 삭제하면 404, 행은 보존
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_다른_사용자의_찜을_삭제하면_404이고_행이_보존된다(client, make_user, make_event, make_interest):
    owner = make_user(username="interest-owner")
    attacker = make_user(username="interest-attacker")
    event = make_event(title="Popup IDOR")

    interest = make_interest(owner, event=event)

    client.force_login(attacker)
    response = client.delete(f"/api/event-interests/{interest.pk}/")

    assert response.status_code == 404
    assert EventInterest.objects.filter(pk=interest.pk).exists()


# ---------------------------------------------------------------------------
# 공존 — 같은 행사에 찜과 참석예정 상태가 동시에 존재
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_같은_행사에_찜과_참석예정_상태가_동시에_존재할_수_있다(client, make_user, make_event, make_interest):
    from archive.models import UserEventStatus

    user = make_user(username="interest-coexist-user")
    event = make_event(title="Popup Coexist")
    interest = make_interest(user, event=event)
    interest_id = interest.id

    client.force_login(user)

    status_response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    assert status_response.status_code == 201
    status_id = status_response.json()["id"]

    assert EventInterest.objects.filter(pk=interest_id, user=user).exists()
    assert UserEventStatus.objects.filter(pk=status_id, user=user, status="planned").exists()

    get_interest = client.get(f"/api/event-interests/{interest_id}/")
    assert get_interest.status_code == 200

    get_status = client.get(f"/api/user-event-statuses/{status_id}/")
    assert get_status.status_code == 200


# ---------------------------------------------------------------------------
# 비로그인 → 403
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_비로그인_사용자가_찜을_등록하면_인증_오류가_된다(client, make_event):
    event = make_event(title="Popup Unauth")

    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_비로그인_사용자가_찜_목록을_조회하면_인증_오류가_된다(client):
    response = client.get("/api/event-interests/")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 생성 스로틀 — 목록에서 여러 행사를 빠르게 연달아 찜할 수 있어 분당 60건.
# GET(목록)은 스로틀 대상이 아님을 함께 확인한다.
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.django_db
def test_찜_생성_요청이_설정된_한도를_초과하면_429로_제한된다(client, make_user, make_event):
    user = make_user(username="interest-create-flood")
    client.force_login(user)

    # 분당 60건 한도: 서로 다른 행사 60개로 채우고 61번째를 확인한다.
    for i in range(60):
        event = make_event(title=f"한도 확인 행사 {i}")
        response = client.post(
            "/api/event-interests/",
            {"event": event.id},
            content_type="application/json",
        )
        assert response.status_code == 201, f"create {i} should succeed"

    over_limit_event = make_event(title="한도 초과 행사")
    throttled = client.post(
        "/api/event-interests/",
        {"event": over_limit_event.id},
        content_type="application/json",
    )

    assert throttled.status_code == 429
    assert EventInterest.objects.count() == 60

    listed = client.get("/api/event-interests/")
    assert listed.status_code == 200
