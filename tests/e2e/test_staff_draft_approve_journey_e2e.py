"""스태프가 드래프트를 승인하면 공개 이벤트가 되는 여정."""
import re

from playwright.sync_api import expect

from drafts.models import EventDraft
from events.models import Event


def test_스태프가_드래프트를_승인하면_공개_이벤트_상세가_열린다(
    page, base_url, verified_user, login_as, make_pending_draft
):
    staff = verified_user(is_staff=True)
    login_as(staff)
    draft = make_pending_draft(
        raw_title="e2e 승인 드래프트", extracted_title="e2e 승인 드래프트"
    )

    page.goto(f"{base_url}/staff/drafts/{draft.id}/")
    page.get_by_role("button", name="승인하고 게시").click()
    page.get_by_role("button", name="예").click()

    success = page.locator("#draft-approve-success")
    expect(success).to_be_visible()
    expect(success).to_contain_text("승인 완료")

    success.get_by_role("link", name=re.compile(r"이벤트 #\d+ 보기")).click()

    expect(page).to_have_url(re.compile(r"/events/\d+/$"))
    expect(page.get_by_role("heading", name="e2e 승인 드래프트")).to_be_visible()

    assert (
        Event.objects.get(official_url=draft.source_url).publish_status
        == Event.PublishStatus.PUBLISHED
    )
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
