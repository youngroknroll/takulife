"""StaffActionLog(스태프 감사 로그) 검증.

승인·거부 등 행위 기록은 추가만 되고 지워지지 않는다. 어드민 조회는
슈퍼유저만 가능하며 일반 스태프는 열람·관리할 수 없다.
"""
import pytest
from django.contrib import admin
from django.test import RequestFactory

from events.models import Event
from staff.admin import StaffActionLogAdmin
from staff.models import StaffActionLog

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_스태프_액션_로그를_생성하면_행위자_행위_대상_드래프트와_메타데이터가_저장된다(make_user, make_draft):
    actor = make_user(is_staff=True)
    draft = make_draft("https://example.com/logged-event")

    entry = StaffActionLog.objects.create(
        actor=actor,
        action="approve",
        target_draft=draft,
        ip_address="127.0.0.1",
        user_agent="pytest-agent",
    )

    entry.refresh_from_db()
    assert entry.actor_id == actor.id
    assert entry.action == "approve"
    assert entry.target_draft_id == draft.id
    assert entry.ip_address == "127.0.0.1"
    assert entry.user_agent == "pytest-agent"
    assert entry.created_at is not None


@pytest.mark.django_db
def test_행위자_사용자를_삭제해도_액션_로그는_남고_행위자_참조만_비워진다(make_user):
    actor = make_user(is_staff=True)
    entry = StaffActionLog.objects.create(actor=actor, action="reject")

    actor.delete()
    entry.refresh_from_db()

    assert entry.actor_id is None


@pytest.mark.django_db
def test_대상_드래프트를_삭제해도_액션_로그는_남고_대상_참조만_비워진다(make_draft):
    draft = make_draft("https://example.com/deleted-draft-log")
    entry = StaffActionLog.objects.create(action="approve", target_draft=draft)

    draft.delete()
    entry.refresh_from_db()

    assert entry.target_draft_id is None


@pytest.mark.django_db
def test_액션_로그_목록은_최신_순으로_정렬된다(make_user):
    actor = make_user(is_staff=True)
    first = StaffActionLog.objects.create(actor=actor, action="approve")
    second = StaffActionLog.objects.create(actor=actor, action="reject")

    entries = list(StaffActionLog.objects.all())

    assert entries == [second, first]


@pytest.mark.django_db
def test_대상_드래프트가_없는_로그의_문자열_표현은_해시_none을_포함하지_않는다(make_user):
    actor = make_user(is_staff=True)
    entry = StaffActionLog.objects.create(
        actor=actor, action=StaffActionLog.Action.HOME_CATEGORIES, target_draft=None
    )

    text = str(entry)

    assert "#None" not in text
    assert text == f"home_categories by {actor.id}"


@pytest.mark.django_db
def test_액션_로그에_대상_이벤트를_지정하면_대상_이벤트가_저장된다(make_user):
    actor = make_user(is_staff=True)
    event = Event.objects.create(title="Logged event", publish_status=Event.PublishStatus.PUBLISHED)

    entry = StaffActionLog.objects.create(
        actor=actor,
        action=StaffActionLog.Action.EVENT_UPDATE,
        target_event=event,
    )

    entry.refresh_from_db()
    assert entry.action == "event_update"
    assert entry.target_event_id == event.id


@pytest.mark.django_db
def test_대상_이벤트를_삭제해도_액션_로그는_남고_대상_참조만_비워진다():
    event = Event.objects.create(title="Deleted event", publish_status=Event.PublishStatus.PUBLISHED)
    entry = StaffActionLog.objects.create(action=StaffActionLog.Action.EVENT_UPDATE, target_event=event)

    event.delete()
    entry.refresh_from_db()

    assert entry.target_event_id is None


@pytest.mark.django_db
def test_대상_이벤트가_있는_로그의_문자열_표현은_이벤트_id를_포함한다(make_user):
    actor = make_user(is_staff=True)
    event = Event.objects.create(title="Logged event", publish_status=Event.PublishStatus.PUBLISHED)
    entry = StaffActionLog.objects.create(
        actor=actor, action=StaffActionLog.Action.EVENT_UPDATE, target_event=event
    )

    text = str(entry)

    assert text == f"event_update #{event.id} by {actor.id}"


@pytest.mark.django_db
def test_일반_스태프는_액션_로그_어드민_조회_권한이_없다(make_user):
    staff_user = make_user(is_staff=True)
    request = RequestFactory().get("/admin/staff/staffactionlog/")
    request.user = staff_user
    log_admin = StaffActionLogAdmin(StaffActionLog, admin.site)

    assert log_admin.has_view_permission(request) is False
    assert log_admin.has_module_permission(request) is False


@pytest.mark.django_db
def test_슈퍼유저는_액션_로그_어드민_조회_권한이_있다(make_user):
    superuser = make_user(is_staff=True, is_superuser=True)
    request = RequestFactory().get("/admin/staff/staffactionlog/")
    request.user = superuser
    log_admin = StaffActionLogAdmin(StaffActionLog, admin.site)

    assert log_admin.has_view_permission(request) is True
    assert log_admin.has_module_permission(request) is True


@pytest.mark.django_db
def test_슈퍼유저도_액션_로그_어드민에서_추가_수정_삭제는_할_수_없다(make_user):
    staff_user = make_user(is_staff=True, is_superuser=True)
    request = RequestFactory().get("/admin/staff/staffactionlog/")
    request.user = staff_user
    log_admin = StaffActionLogAdmin(StaffActionLog, admin.site)

    assert log_admin.has_add_permission(request) is False
    assert log_admin.has_change_permission(request) is False
    assert log_admin.has_delete_permission(request) is False


@pytest.mark.django_db
def test_이벤트_crud_액션_값은_필드_길이_제한_안에서_정상_저장된다(make_event):
    """행사 CRUD 액션 값이 Action 필드 max_length=16을 넘으면 저장 시 DataError가 나야 한다."""
    event = make_event(official_url="https://example.com/crud-actions")

    for action in (
        StaffActionLog.Action.EVENT_CREATE,
        StaffActionLog.Action.EVENT_UNPUBLISH,
        StaffActionLog.Action.EVENT_REPUBLISH,
        StaffActionLog.Action.EVENT_DELETE,
    ):
        assert len(action) <= 16
        entry = StaffActionLog.objects.create(action=action, target_event=event)
        entry.refresh_from_db()
        assert entry.action == action
