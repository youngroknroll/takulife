"""스태프 이벤트 목록 인라인 단건 비공개·재게시(/publish-status/)와 검증(/verified/) 검증.

두 엔드포인트는 트랙 24 일괄 비공개와 달리 항목이 하나뿐이라 항상 200(값
오류만 400) 또는 404이고, 목표 상태를 그대로 설정한다(토글이 아니다).
"""
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from events.models import Event
from staff.models import StaffActionLog

pytestmark = pytest.mark.web


def publish_status_url(event_id):
    return reverse("staff:event-publish-status", args=[event_id])


def verified_url(event_id):
    return reverse("staff:event-verified", args=[event_id])


# --- publish-status 권한·메서드 게이트 -------------------------------------


@pytest.mark.django_db
def test_익명_사용자는_이벤트_목표_게시_상태_설정을_할_수_없다(client, make_event):
    event = make_event()

    response = client.post(
        publish_status_url(event.id),
        data={"publish_status": "draft"},
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_일반_사용자는_이벤트_목표_게시_상태_설정을_할_수_없다(client, make_user, make_event):
    user = make_user()
    client.force_login(user)
    event = make_event()

    response = client.post(
        publish_status_url(event.id),
        data={"publish_status": "draft"},
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_publish_status_경로에_GET으로_접근하면_허용되지_않는다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event()

    response = client.get(publish_status_url(event.id))

    assert response.status_code == 405
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.PUBLISHED


@pytest.mark.django_db
def test_존재하지_않는_이벤트_id로_게시_상태_설정을_요청하면_404가_된다(staff_client):
    staff, client = staff_client()

    response = client.post(
        publish_status_url(999999),
        data={"publish_status": "draft"},
        content_type="application/json",
    )

    assert response.status_code == 404


# --- publish-status 본문 값 검증 ---------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"publish_status": "archived"},
        {"publish_status": 123},
    ],
    ids=["키_없음", "목록에_없는_값", "문자열이_아닌_값"],
)
def test_publish_status_값이_유효하지_않으면_이벤트_게시_상태_설정을_거부한다(
    staff_client, make_event, body
):
    staff, client = staff_client()
    event = make_event()

    response = client.post(
        publish_status_url(event.id), data=body, content_type="application/json"
    )

    assert response.status_code == 400
    assert "publish_status" in response.json()
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.PUBLISHED


# --- publish-status 정상 전환 ------------------------------------------------


@pytest.mark.django_db
def test_게시된_이벤트를_publish_status_draft로_설정하면_비공개로_전환되고_감사_로그가_남는다(
    staff_client, make_event
):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/inline-unpublish")

    response = client.post(
        publish_status_url(event.id),
        data={"publish_status": "draft"},
        REMOTE_ADDR="203.0.113.7",
        HTTP_USER_AGENT="pytest-agent/1.0",
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": event.id,
        "publish_status": "draft",
        "changed": True,
        "quality_badges": [],
    }
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT

    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_UNPUBLISH
    assert log.actor_id == staff.id
    assert log.ip_address == "203.0.113.7"
    assert log.user_agent == "pytest-agent/1.0"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target_status,use_draft_fixture",
    [("draft", True), ("published", False)],
    ids=["이미_비공개", "이미_게시"],
)
def test_이미_목표_게시_상태인_이벤트는_변경과_로그_없이_changed_false를_응답한다(
    staff_client, make_event, make_draft_event, target_status, use_draft_fixture
):
    staff, client = staff_client()
    if use_draft_fixture:
        event = make_draft_event(official_url="https://example.com/inline-already-draft")
    else:
        event = make_event(official_url="https://example.com/inline-already-published")

    response = client.post(
        publish_status_url(event.id),
        data={"publish_status": target_status},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is False
    assert body["publish_status"] == target_status
    event.refresh_from_db()
    assert event.publish_status == target_status
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_초안_이벤트를_publish_status_published로_설정하면_게시되고_서버가_계산한_품질_배지를_응답한다(
    staff_client, make_draft_event
):
    staff, client = staff_client()
    event = make_draft_event(
        title="종료된 초안",
        official_url="https://example.com/inline-republish-ended",
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() - timedelta(days=1),
        region="seoul",
    )

    response = client.post(
        publish_status_url(event.id),
        data={"publish_status": "published"},
        content_type="application/json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is True
    assert body["quality_badges"] == ["종료됐지만 게시 중"]
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.PUBLISHED

    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_REPUBLISH


# --- publish-status 재게시 불변식 위반 5종 -----------------------------------
# 토글 뷰(staff/views/events.py except 절)와 같은 문구를 리터럴로 복사한다 —
# 상수를 공유하기 전까지 이 문구가 그대로임을 이 테스트가 보증한다.


def _setup_missing_official_url(make_draft_event, make_event):
    return make_draft_event(
        title="유효한 제목",
        official_url="",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=10),
        category="popup_store",
        region="seoul",
    )


def _setup_missing_title(make_draft_event, make_event):
    return make_draft_event(
        title="",
        official_url="https://example.com/inline-republish-missing-title",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=10),
        category="popup_store",
        region="seoul",
    )


def _setup_invalid_period(make_draft_event, make_event):
    return make_draft_event(
        title="유효한 제목",
        official_url="https://example.com/inline-republish-invalid-period",
        start_date=date.today() + timedelta(days=10),
        end_date=date.today(),
        category="popup_store",
        region="seoul",
    )


def _setup_invalid_category(make_draft_event, make_event):
    return make_draft_event(
        title="유효한 제목",
        official_url="https://example.com/inline-republish-invalid-category",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=10),
        category="존재하지-않는-카테고리",
        region="seoul",
    )


def _setup_invalid_region(make_draft_event, make_event):
    return make_draft_event(
        title="유효한 제목",
        official_url="https://example.com/inline-republish-invalid-region",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=10),
        category="popup_store",
        region="존재하지-않는-지역",
    )


# "공식_URL_중복"(DuplicateOfficialUrlError)은 여기서 재현할 수 없다 — official_url이
# DB 유일 제약이라, 두 번째 draft를 같은 URL로 만드는 Given 자체가 IntegrityError로
# 죽는다. 재게시 경로에서 이 예외는 문구 표에는 있어도 실제로 도달 불가(오케스트레이터
# 실측 지적, 2026-09-09). U8은 5종만 남긴다.
_U8_CASES = [
    ("공식_URL_없음", _setup_missing_official_url, "공식 URL이 없어 다시 게시할 수 없습니다."),
    ("제목_없음", _setup_missing_title, "제목이 없어 다시 게시할 수 없습니다."),
    ("기간_역전", _setup_invalid_period, "종료일이 시작일보다 빨라 다시 게시할 수 없습니다."),
    (
        "카테고리_무효",
        _setup_invalid_category,
        "카테고리가 목록에 없는 값이라 다시 게시할 수 없습니다. 먼저 수정하세요.",
    ),
    (
        "지역_무효",
        _setup_invalid_region,
        "지역이 목록에 없는 값이라 다시 게시할 수 없습니다. 먼저 수정하세요.",
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "setup,expected_message",
    [(case[1], case[2]) for case in _U8_CASES],
    ids=[case[0] for case in _U8_CASES],
)
def test_재게시_불변식을_위반한_초안_이벤트는_publish_status_published_설정이_거부되고_토글_뷰와_같은_문구를_응답한다(
    staff_client, make_draft_event, make_event, setup, expected_message
):
    staff, client = staff_client()
    event = setup(make_draft_event, make_event)

    response = client.post(
        publish_status_url(event.id),
        data={"publish_status": "published"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"detail": expected_message}
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_publish_status_설정은_대상_행을_잠그고_읽는다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/inline-lock")

    with CaptureQueriesContext(connection) as ctx:
        response = client.post(
            publish_status_url(event.id),
            data={"publish_status": "draft"},
            content_type="application/json",
        )

    assert response.status_code == 200
    locking_queries = [q for q in ctx.captured_queries if "FOR UPDATE" in q["sql"].upper()]
    assert locking_queries, ctx.captured_queries


# --- verified 권한·메서드 게이트 ---------------------------------------------


@pytest.mark.django_db
def test_익명_사용자는_이벤트_검증_완료_처리를_할_수_없다(client, make_event):
    event = make_event()

    response = client.post(verified_url(event.id))

    assert response.status_code == 403


@pytest.mark.django_db
def test_일반_사용자는_이벤트_검증_완료_처리를_할_수_없다(client, make_user, make_event):
    user = make_user()
    client.force_login(user)
    event = make_event()

    response = client.post(verified_url(event.id))

    assert response.status_code == 403


@pytest.mark.django_db
def test_verified_경로에_GET으로_접근하면_허용되지_않는다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event()

    response = client.get(verified_url(event.id))

    assert response.status_code == 405
    event.refresh_from_db()
    assert event.verified_at is None


@pytest.mark.django_db
def test_존재하지_않는_이벤트_id로_검증_완료를_요청하면_404가_된다(staff_client):
    staff, client = staff_client()

    response = client.post(verified_url(999999))

    assert response.status_code == 404


@pytest.mark.django_db
def test_스태프가_재확인_대상_이벤트를_검증_완료_처리하면_검증_시각이_기록되고_시작_임박_배지가_사라진다(
    staff_client, make_event
):
    staff, client = staff_client()
    event = make_event(
        official_url="https://example.com/inline-verify",
        start_date=date.today() + timedelta(days=7),
        end_date=date.today() + timedelta(days=30),
        region="seoul",
        verified_at=None,
    )

    response = client.post(verified_url(event.id), content_type="application/json")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == event.id
    assert isinstance(body["verified_at"], str) and body["verified_at"]
    assert body["quality_badges"] == []

    event.refresh_from_db()
    assert event.verified_at is not None

    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_VERIFY


@pytest.mark.django_db
def test_비공개_이벤트를_검증_완료_처리하면_기록은_남지만_품질_배지는_빈_목록이다(
    staff_client, make_draft_event
):
    staff, client = staff_client()
    # 게시 상태였다면 "종료됐지만 게시 중" 배지가 붙을 기간이지만, 비공개라
    # 배지 계산 자체를 건너뛴다는 것이 이 테스트의 유일한 관심사다.
    event = make_draft_event(
        official_url="https://example.com/inline-verify-draft-ended",
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() - timedelta(days=10),
        region="seoul",
        verified_at=None,
    )

    response = client.post(verified_url(event.id), content_type="application/json")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["verified_at"], str) and body["verified_at"]
    assert body["quality_badges"] == []

    event.refresh_from_db()
    assert event.verified_at is not None

    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_VERIFY
