"""스태프가 이벤트를 골라 비공개로 설정하면 공개 목록에서 사라지는 여정."""
from playwright.sync_api import expect

from events.models import Event


def test_스태프가_이벤트를_골라_비공개로_설정하면_공개_목록에서_사라진다(
    page, base_url, verified_user, login_as, make_published_event
):
    staff = verified_user(is_staff=True)
    login_as(staff)
    target = make_published_event("e2e 비공개 대상")
    keep = make_published_event("e2e 계속 공개")

    page.goto(f"{base_url}/staff/events/")
    page.get_by_role("checkbox", name="e2e 비공개 대상 선택").check()
    page.get_by_role("button", name="선택 항목 비공개로 설정").click()
    page.get_by_role("button", name="예").click()

    expect(page.locator("#event-bulk-result")).to_have_text("1건 모두 비공개 완료.")

    page.goto(f"{base_url}/events/")
    expect(page.get_by_role("link", name="e2e 계속 공개")).to_be_visible()
    expect(page.get_by_role("link", name="e2e 비공개 대상")).to_have_count(0)

    target.refresh_from_db()
    keep.refresh_from_db()
    assert target.publish_status == Event.PublishStatus.DRAFT
    assert keep.publish_status == Event.PublishStatus.PUBLISHED
