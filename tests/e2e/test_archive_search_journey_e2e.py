"""아카이브 검색어를 입력하면 새로고침 없이 결과가 좁혀지는 여정
(디바운스 + 조각 교체 + pushState는 브라우저 JS가 아니면 확인할 수 없다)."""
import re

from playwright.sync_api import expect

from archive.models import UserEventStatus


def test_아카이브_검색어를_입력하면_새로고침_없이_결과가_좁혀지고_링크로_이동한다(
    page, base_url, verified_user, login_as, make_published_event
):
    user = verified_user()
    login_as(user)
    summer = make_published_event("e2e 여름 팝업스토어")
    winter = make_published_event("e2e 겨울 콜라보 카페")
    UserEventStatus.objects.create(
        user=user, event=summer, status=UserEventStatus.Status.PLANNED
    )
    UserEventStatus.objects.create(
        user=user, event=winter, status=UserEventStatus.Status.PLANNED
    )

    page.goto(f"{base_url}/archive/statuses/")
    page.get_by_label("아카이브 검색").fill("여름")

    results = page.locator("#archive-results")
    expect(results.get_by_role("link", name="e2e 여름 팝업스토어")).to_be_visible()
    expect(results.get_by_role("link", name="e2e 겨울 콜라보 카페")).to_have_count(0)
    expect(page).to_have_url(re.compile(r"q="))

    results.get_by_role("link", name="e2e 여름 팝업스토어").click()

    expect(page).to_have_url(f"{base_url}/events/{summer.id}/")
