"""게시 상태 토글 + 참조 보호 하드 삭제 검증.

/staff/events/<pk>/toggle-publish/(게시 취소↔재게시)와
/staff/events/<pk>/delete/(서버 렌더 2단계 확인)를 다룬다. 둘 다 수정 페이지
폼에서만 오는 POST 전용 SSR 액션이며 JSON API가 아니다.
"""
import datetime

import pytest

from archive.models import CollectionItem, EventInterest
from events.models import Event
from staff.models import StaffActionLog


def _toggle_url(event):
    return f"/staff/events/{event.pk}/toggle-publish/"


def _delete_url(event):
    return f"/staff/events/{event.pk}/delete/"


pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_비로그인_사용자가_게시_토글을_요청하면_로그인_페이지로_리다이렉트된다(client, make_event):
    event = make_event(official_url="https://example.com/toggle-anon")

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next=/staff/events/{event.pk}/toggle-publish/"


@pytest.mark.django_db
def test_스태프가_아닌_사용자가_게시_토글을_요청하면_403을_응답한다(client, make_user, make_event):
    user = make_user()
    client.force_login(user)
    event = make_event(official_url="https://example.com/toggle-403")

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 403


@pytest.mark.django_db
def test_게시_토글_경로에_GET으로_접근하면_405를_응답하고_상태를_바꾸지_않는다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/toggle-get")

    resp = client.get(_toggle_url(event))

    assert resp.status_code == 405
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.PUBLISHED


@pytest.mark.django_db
def test_게시된_이벤트를_토글하면_게시_취소되고_감사_로그를_남긴다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/toggle-unpublish")

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 302
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT
    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_UNPUBLISH
    assert log.actor_id == staff.id


@pytest.mark.django_db
def test_초안_이벤트를_토글하면_재게시되고_감사_로그를_남긴다(staff_client, make_draft_event):
    staff, client = staff_client()
    event = make_draft_event(
        title="초안", official_url="https://example.com/toggle-republish"
    )

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 302
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    log = StaffActionLog.objects.get(target_event=event)
    assert log.action == StaffActionLog.Action.EVENT_REPUBLISH


@pytest.mark.django_db
def test_제목이_없는_초안_이벤트는_재게시_토글이_거부되고_감사_로그를_남기지_않는다(staff_client, make_draft_event):
    staff, client = staff_client()
    event = make_draft_event(title="", official_url="https://example.com/toggle-broken")

    resp = client.post(_toggle_url(event))

    assert resp.status_code == 302
    event.refresh_from_db()
    assert event.publish_status == Event.PublishStatus.DRAFT
    assert not StaffActionLog.objects.filter(target_event=event).exists()


@pytest.mark.django_db
def test_비로그인_사용자가_삭제를_요청하면_로그인_페이지로_리다이렉트된다(client, make_event):
    event = make_event(official_url="https://example.com/delete-anon")

    resp = client.post(_delete_url(event))

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next=/staff/events/{event.pk}/delete/"


@pytest.mark.django_db
def test_스태프가_아닌_사용자가_삭제를_요청하면_403을_응답한다(client, make_user, make_event):
    user = make_user()
    client.force_login(user)
    event = make_event(official_url="https://example.com/delete-403")

    resp = client.post(_delete_url(event))

    assert resp.status_code == 403


@pytest.mark.django_db
def test_삭제_경로에_GET으로_접근하면_405를_응답하고_삭제하지_않는다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(official_url="https://example.com/delete-get")

    resp = client.get(_delete_url(event))

    assert resp.status_code == 405
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_삭제_첫_POST는_삭제하지_않고_확인_화면을_보여준다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="삭제 대상", official_url="https://example.com/delete-confirm-step")

    resp = client.post(_delete_url(event))

    assert resp.status_code == 200
    assert "삭제" in resp.content.decode()
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_삭제_확인_POST는_이벤트를_삭제하고_감사_로그를_남긴_뒤_목록으로_리다이렉트된다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="삭제 대상", official_url="https://example.com/delete-confirmed")

    resp = client.post(_delete_url(event), {"confirmed": "yes"})

    assert resp.status_code == 302
    assert resp.url == "/staff/events/"
    assert not Event.objects.filter(pk=event.pk).exists()
    log = StaffActionLog.objects.get(action=StaffActionLog.Action.EVENT_DELETE)
    assert log.actor_id == staff.id
    assert log.target_event_id is None


@pytest.mark.django_db
def test_삭제_후_리다이렉트는_목록_필터_쿼리를_유지한다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="삭제 대상", official_url="https://example.com/delete-filter-prg")

    resp = client.post(
        f"{_delete_url(event)}?warning=missing_region", {"confirmed": "yes"}
    )

    assert resp.status_code == 302
    assert resp.url == "/staff/events/?warning=missing_region"


@pytest.mark.django_db
def test_아카이브_참조가_있는_이벤트는_삭제가_차단되고_감사_로그를_남기지_않는다(staff_client, make_user, make_event):
    staff, client = staff_client()
    event = make_event(title="찜된 행사", official_url="https://example.com/delete-blocked")
    interested_user = make_user()
    EventInterest.objects.create(user=interested_user, event=event)

    resp = client.post(_delete_url(event), {"confirmed": "yes"})

    assert resp.status_code == 302
    assert Event.objects.filter(pk=event.pk).exists()
    assert not StaffActionLog.objects.filter(action=StaffActionLog.Action.EVENT_DELETE).exists()


@pytest.mark.django_db
def test_참조가_있는_이벤트의_수정_페이지는_삭제_버튼_대신_참조_건수를_보여준다(staff_client, make_user, make_event):
    staff, client = staff_client()
    event = make_event(title="찜된 행사", official_url="https://example.com/edit-blocked-delete")
    interested_user = make_user()
    EventInterest.objects.create(user=interested_user, event=event)

    resp = client.get(f"/staff/events/{event.pk}/edit/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "찜 1" in content
    assert f'action="/staff/events/{event.pk}/delete/"' not in content


@pytest.mark.django_db
def test_참조가_없는_이벤트의_수정_페이지는_삭제_버튼을_보여준다(staff_client, make_event):
    staff, client = staff_client()
    event = make_event(title="깨끗한 행사", official_url="https://example.com/edit-allowed-delete")

    resp = client.get(f"/staff/events/{event.pk}/edit/")

    assert resp.status_code == 200
    assert f'action="/staff/events/{event.pk}/delete/"' in resp.content.decode()


@pytest.mark.django_db
def test_컬렉션_항목이_참조하는_이벤트의_수정_페이지는_삭제_버튼_대신_컬렉션_참조_건수를_보여준다(
    staff_client, make_user, make_event
):
    staff, client = staff_client()
    event = make_event(
        title="컬렉션 참조 행사", official_url="https://example.com/edit-blocked-collection"
    )
    owner = make_user()
    CollectionItem.objects.create(user=owner, name="참조 굿즈", event=event)

    resp = client.get(f"/staff/events/{event.pk}/edit/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "컬렉션 1" in content
    assert f'action="/staff/events/{event.pk}/delete/"' not in content


@pytest.mark.django_db
def test_컬렉션_참조로_삭제가_차단되면_안내_메시지에_컬렉션_참조_건수가_포함된다(
    staff_client, make_user, make_event
):
    staff, client = staff_client()
    event = make_event(
        title="컬렉션 참조 삭제 차단", official_url="https://example.com/delete-blocked-collection"
    )
    owner = make_user()
    CollectionItem.objects.create(user=owner, name="차단용 굿즈", event=event)

    resp = client.post(_delete_url(event), {"confirmed": "yes"}, follow=True)

    assert Event.objects.filter(pk=event.pk).exists()
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert "컬렉션 1" in messages_text
