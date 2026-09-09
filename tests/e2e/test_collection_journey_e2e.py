"""컬렉션 항목 생성·수정·삭제 여정 — 각각 다른 JS fetch(POST/PATCH/DELETE)라
테스트를 셋으로 나눈다."""
import re

from playwright.sync_api import expect

from archive.models import CollectionItem


def test_컬렉션_항목을_만들면_목록에_나타나고_상세가_열린다(
    page, base_url, verified_user, login_as
):
    user = verified_user()
    login_as(user)

    page.goto(f"{base_url}/collection/new/")
    page.get_by_label("이름").fill("e2e 아크릴 스탠드")
    page.get_by_role("button", name="항목 저장").click()

    expect(page).to_have_url(f"{base_url}/collection/")

    page.get_by_role("link", name="e2e 아크릴 스탠드").click()

    expect(page).to_have_url(re.compile(r"/collection/\d+/$"))
    expect(page.get_by_role("heading", name="e2e 아크릴 스탠드")).to_be_visible()

    assert CollectionItem.objects.filter(user=user, name="e2e 아크릴 스탠드").count() == 1


def test_컬렉션_항목_이름을_고치면_상세가_새_이름을_보여준다(
    page, base_url, verified_user, login_as
):
    user = verified_user()
    login_as(user)
    item = CollectionItem.objects.create(user=user, name="e2e 이전 이름")

    page.goto(f"{base_url}/collection/{item.id}/")
    page.get_by_role("link", name="수정").click()
    page.get_by_label("이름").fill("e2e 새 이름")
    page.get_by_role("button", name="저장").click()

    expect(page).to_have_url(f"{base_url}/collection/{item.id}/")
    expect(page.get_by_role("heading", name="e2e 새 이름")).to_be_visible()

    item.refresh_from_db()
    assert item.name == "e2e 새 이름"


def test_컬렉션_항목_삭제를_확인하면_목록이_빈_상태가_되고_취소하면_남는다(
    page, base_url, verified_user, login_as
):
    user = verified_user()
    login_as(user)
    item = CollectionItem.objects.create(user=user, name="e2e 삭제 대상")

    page.goto(f"{base_url}/collection/{item.id}/")
    page.get_by_role("button", name="굿즈 삭제").click()
    page.get_by_role("button", name="아니오").click()

    expect(page).to_have_url(f"{base_url}/collection/{item.id}/")
    assert CollectionItem.objects.filter(id=item.id).count() == 1

    page.get_by_role("button", name="굿즈 삭제").click()
    page.get_by_role("button", name="예").click()

    expect(page).to_have_url(f"{base_url}/collection/")
    expect(page.get_by_text("아직 등록한 컬렉션이 없어요")).to_be_visible()
    assert CollectionItem.objects.filter(id=item.id).count() == 0
