"""이벤트 생성 페이지(/staff/events/new/) 검증.

생성은 반드시 create_published_event를 거치는 유일한 경로이며, 규칙 위반은
필드 오류로 매핑되고 성공 시 StaffActionLog(event_create)를 남긴다.
"""
import pytest

from events.models import Event
from staff.models import StaffActionLog

CREATE_URL = "/staff/events/new/"

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_비로그인_사용자가_이벤트_생성_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    resp = client.get(CREATE_URL)

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next={CREATE_URL}"


@pytest.mark.django_db
def test_스태프가_아닌_사용자가_이벤트_생성_페이지에_접근하면_403을_응답한다(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get(CREATE_URL)

    assert resp.status_code == 403


@pytest.mark.django_db
def test_이벤트_생성_페이지_GET은_빈_폼을_렌더링한다(staff_client):
    staff, client = staff_client()

    resp = client.get(CREATE_URL)

    assert resp.status_code == 200
    assert 'value=""' in resp.content.decode()


@pytest.mark.django_db
def test_이벤트_생성_폼_제출은_게시된_이벤트를_생성하고_감사_로그를_남긴다(staff_client, staff_event_payload):
    staff, client = staff_client()

    resp = client.post(CREATE_URL, staff_event_payload())

    assert resp.status_code == 302
    event = Event.objects.get(official_url="https://example.com/new-event")
    assert event.title == "새 이벤트"
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.category == "popup_store"

    log = StaffActionLog.objects.get(target_event=event)
    assert log.actor_id == staff.id
    assert log.action == StaffActionLog.Action.EVENT_CREATE


@pytest.mark.django_db
def test_제목이_빈_값이면_400과_필드_오류를_응답하고_이벤트를_생성하지_않는다(staff_client, staff_event_payload):
    staff, client = staff_client()

    resp = client.post(
        CREATE_URL,
        staff_event_payload(title="   ", official_url="https://example.com/blank-title-create"),
    )

    assert resp.status_code == 400
    assert "제목" in resp.content.decode()
    assert not Event.objects.filter(official_url="https://example.com/blank-title-create").exists()


@pytest.mark.django_db
def test_공식_URL이_중복되면_400과_필드_오류를_응답하고_이벤트를_생성하지_않는다(
    staff_client, make_event, staff_event_payload
):
    staff, client = staff_client()
    make_event(title="기존 행사", official_url="https://example.com/taken-create")

    resp = client.post(
        CREATE_URL,
        staff_event_payload(official_url="https://example.com/taken-create"),
    )

    assert resp.status_code == 400
    assert "공식 URL" in resp.content.decode()
    assert Event.objects.filter(official_url="https://example.com/taken-create").count() == 1


@pytest.mark.django_db
def test_이벤트_목록_페이지는_생성_페이지로_가는_링크를_포함한다(staff_client):
    staff, client = staff_client()

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    assert CREATE_URL in resp.content.decode()
