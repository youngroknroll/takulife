"""방문 기록을 남기면 방문 기록 목록에 나타나는 여정.

선택 대상 목록(`selectable_events`)은 저장된 원본 'planned' 상태만 보여주므로
(archive/queries.py list_user_planned_events), Given에서 게시 이벤트에 이미
방문 예정 상태를 만들어 둔다."""
from playwright.sync_api import expect

from archive.models import UserEventStatus, VisitRecord


def test_방문_기록을_남기면_방문_기록_목록에_나타난다(
    page, base_url, verified_user, login_as, make_published_event
):
    user = verified_user()
    login_as(user)
    event = make_published_event("e2e 콜라보 카페")
    UserEventStatus.objects.create(
        user=user, event=event, status=UserEventStatus.Status.PLANNED
    )

    page.goto(f"{base_url}/archive/visits/new/")
    page.get_by_label("대상").select_option(label=event.title)
    page.get_by_label("방문 날짜").fill("2026-09-01")
    page.get_by_role("button", name="기록 저장").click()

    expect(page).to_have_url(f"{base_url}/archive/visits/")

    results = page.locator("#archive-results")
    expect(results.get_by_role("link", name=event.title)).to_be_visible()

    assert VisitRecord.objects.filter(user=user).count() == 1
