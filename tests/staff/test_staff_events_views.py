"""스태프 행사 목록(/staff/events/) 인증 게이트와 경고/게시상태 필터링, 페이지네이션 검증."""
import re
from datetime import date, timedelta

import pytest

from events.models import Event

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_비로그인_사용자가_스태프_행사_목록에_접근하면_로그인_페이지로_리다이렉트된다(client):
    resp = client.get("/staff/events/")

    assert resp.status_code == 302
    assert resp.url == "/accounts/login/?next=/staff/events/"


@pytest.mark.django_db
def test_스태프가_아닌_사용자가_스태프_행사_목록에_접근하면_403이_응답된다(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get("/staff/events/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_스태프가_행사_목록에_접근하면_게시된_행사가_노출된다(staff_client, make_event):
    staff, client = staff_client()
    make_event(title="공개 행사")

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    assert "공개 행사" in resp.content.decode()


@pytest.mark.django_db
def test_스태프_행사_목록은_기본적으로_초안_행사도_함께_보여준다(staff_client, make_draft_event):
    staff, client = staff_client()
    make_draft_event(title="비공개 초안", official_url=None)

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    assert "비공개 초안" in resp.content.decode()


@pytest.mark.django_db
def test_경고_필터를_적용하면_해당_경고에_해당하는_행사만_노출된다(staff_client, make_event):
    staff, client = staff_client()
    make_event(title="URL 없는 행사", official_url=None)
    make_event(
        title="깨끗한 행사",
        official_url="https://example.com/clean",
        region="서울",
        start_date=date(2020, 1, 1),
        end_date=date(2020, 12, 31),
    )

    resp = client.get("/staff/events/?warning=missing_official_url")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "URL 없는 행사" in content
    assert "깨끗한 행사" not in content
    assert resp.context["selected_warning"] == "missing_official_url"


@pytest.mark.django_db
def test_알_수_없는_경고_값을_지정하면_필터_없이_전체_행사가_노출된다(staff_client, make_event):
    staff, client = staff_client()
    make_event(title="아무 행사")

    resp = client.get("/staff/events/?warning=not-a-real-warning")

    assert resp.status_code == 200
    assert resp.context["selected_warning"] == ""
    assert "아무 행사" in resp.content.decode()


@pytest.mark.django_db
def test_게시_상태_필터를_적용하면_해당_상태의_행사만_노출된다(staff_client, make_event, make_draft_event):
    staff, client = staff_client()
    make_event(title="게시된 행사")
    make_draft_event(title="초안 행사", official_url=None)

    resp = client.get("/staff/events/?publish_status=draft")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "초안 행사" in content
    assert "게시된 행사" not in content
    assert resp.context["selected_publish_status"] == "draft"


@pytest.mark.django_db
def test_두번째_페이지를_요청하면_남은_건수만큼_행사가_노출된다(staff_client, make_event):
    from events.queries import STAFF_EVENT_LISTING_PAGE_SIZE

    staff, client = staff_client()
    for i in range(STAFF_EVENT_LISTING_PAGE_SIZE + 1):
        make_event(title=f"행사 {i}")

    resp = client.get("/staff/events/?page=2")

    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2
    assert len(resp.context["page_obj"].object_list) == 1


@pytest.mark.django_db
def test_종료됐지만_게시중인_경고_필터는_서버의_오늘_날짜를_기준으로_판정한다(staff_client, make_event):
    staff, client = staff_client()
    make_event(
        title="종료된 행사",
        official_url="https://example.com/ended",
        end_date=date.today() - timedelta(days=1),
    )
    make_event(
        title="진행중 행사",
        official_url="https://example.com/ongoing",
        end_date=date.today() + timedelta(days=1),
    )

    resp = client.get("/staff/events/?warning=ended_still_published")

    content = resp.content.decode()
    assert "종료된 행사" in content
    assert "진행중 행사" not in content


@pytest.mark.django_db
def test_재확인_필요_경고_필터를_적용하면_해당_경고에_해당하는_행사만_노출된다(staff_client, make_event):
    staff, client = staff_client()
    make_event(
        title="시작임박미확인행사",
        official_url="https://example.com/needs-reverify",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=10),
    )
    make_event(
        title="여유있는행사",
        official_url="https://example.com/plenty-of-time",
        start_date=date.today() + timedelta(days=30),
        end_date=date.today() + timedelta(days=40),
    )

    resp = client.get("/staff/events/?warning=needs_reverification")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "시작임박미확인행사" in content
    assert "여유있는행사" not in content
    assert resp.context["selected_warning"] == "needs_reverification"


def _row_slice(content, event_id):
    idx = content.index(f'events-id-cell">{event_id}</td>')
    start = content.rfind("<tr", 0, idx)
    end = content.find("</tr>", idx)
    return content[start:end]


@pytest.mark.django_db
def test_게시_행에만_일괄_선택_체크박스가_있고_비공개_행에는_없다(staff_client, make_event, make_draft_event):
    staff, client = staff_client()
    published = make_event(official_url="https://example.com/bulk-select-published")
    draft = make_draft_event(official_url="https://example.com/bulk-select-draft")

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    content = resp.content.decode()
    published_row = _row_slice(content, published.id)
    draft_row = _row_slice(content, draft.id)
    assert "data-event-select" in published_row
    assert "data-event-select" not in draft_row
    assert len(re.findall(r"<col[\s>]", content)) == 8


@pytest.mark.django_db
def test_게시_행이_있으면_일괄_선택_바와_실패_사유_표시_영역이_있다(staff_client, make_event):
    staff, client = staff_client()
    make_event(official_url="https://example.com/bulk-toolbar-present")

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'id="event-bulk-toolbar"' in content
    assert "data-selected-publish-status=" in content
    assert "data-bulk-fail-reason-host" in content
    assert 'id="event-bulk-empty"' in content


@pytest.mark.django_db
def test_게시_행이_없는_페이지에는_일괄_선택_바가_없다(staff_client, make_draft_event):
    staff, client = staff_client()
    make_draft_event(official_url="https://example.com/bulk-toolbar-absent")

    resp = client.get("/staff/events/?publish_status=draft")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'id="event-bulk-toolbar"' not in content


@pytest.mark.django_db
def test_필터_없이도_게시_행이_없는_페이지에는_일괄_선택_바가_없다(staff_client, make_draft_event):
    staff, client = staff_client()
    make_draft_event(official_url="https://example.com/bulk-toolbar-absent-no-filter")

    resp = client.get("/staff/events/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'id="event-bulk-toolbar"' not in content
    assert 'id="event-bulk-empty"' not in content
