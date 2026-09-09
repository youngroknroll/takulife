"""이벤트 상세에서 방문 예정을 누르면 아카이브 일정에 나타나는 여정."""
from playwright.sync_api import expect

from archive.models import UserEventStatus


def test_이벤트_상세에서_방문_예정을_누르면_아카이브_일정에_나타난다(
    page, base_url, verified_user, login_as, make_published_event
):
    user = verified_user()
    login_as(user)
    event = make_published_event("e2e 여름 팝업")

    page.goto(f"{base_url}/events/{event.id}/")
    page.get_by_role("button", name="방문 예정").click()

    expect(page.get_by_text("현재 상태: 방문 예정")).to_be_visible()

    page.goto(f"{base_url}/archive/statuses/")
    results = page.locator("#archive-results")
    expect(results.get_by_role("link", name=event.title)).to_be_visible()
    expect(results.get_by_text("방문 예정")).to_be_visible()

    assert (
        UserEventStatus.objects.filter(
            user=user, event=event, status="planned"
        ).count()
        == 1
    )
