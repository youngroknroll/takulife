"""행사 검증 완료 액션(/staff/events/<pk>/verify/) 검증.

게시된 행사에 verified_at을 기록하고 StaffActionLog를 남기는 서버 렌더 액션이며,
수정 페이지 폼에서만 오는 것으로 JSON API가 아니다.
"""
import pytest

from staff.models import StaffActionLog

pytestmark = pytest.mark.web


def _verify_url(event):
    return f"/staff/events/{event.pk}/verify/"


@pytest.mark.django_db
def test_비로그인_사용자가_행사_검증_완료를_요청하면_로그인_페이지로_리다이렉트된다(client, make_event):
    event = make_event(official_url="https://example.com/verify-anon")

    resp = client.post(_verify_url(event))

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next=/staff/events/{event.pk}/verify/"
    event.refresh_from_db()
    assert event.verified_at is None


@pytest.mark.django_db
def test_스태프가_아닌_사용자가_행사_검증_완료를_요청하면_403이_된다(client, make_user, make_event):
    user = make_user()
    client.force_login(user)
    event = make_event(official_url="https://example.com/verify-403")

    resp = client.post(_verify_url(event))

    assert resp.status_code == 403
    event.refresh_from_db()
    assert event.verified_at is None


@pytest.mark.django_db
def test_행사_검증_완료_경로에_GET으로_접근하면_허용되지_않는다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/verify-get")

    resp = client.get(_verify_url(event))

    assert resp.status_code == 405
    event.refresh_from_db()
    assert event.verified_at is None


@pytest.mark.django_db
def test_스태프가_행사_검증_완료를_요청하면_검증_시각이_기록되고_활동_로그가_남는다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/verify-success")

    client.post(_verify_url(event))

    event.refresh_from_db()
    assert event.verified_at is not None

    assert StaffActionLog.objects.filter(target_event=event).count() == 1
    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_VERIFY
    assert log.target_event_id == event.id
