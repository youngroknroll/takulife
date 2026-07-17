"""core.views.mypage — /mypage/ SSR page: login gate + 4-count summary context.

The 4 counts reuse archive.queries' existing aggregate functions (see
core/views.py's archive_* views for the same pattern) — this file arranges
raw archive.models rows and asserts on the rendered context/response only,
never the query layer itself (test-layer purity guard, see
tests/core/test_architecture_boundaries.py).
"""
import pytest

from archive.models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
)

MYPAGE_URL = "/mypage/"

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_비로그인_사용자가_마이페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get(MYPAGE_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_로그인_사용자가_마이페이지에_접근하면_200을_응답한다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(MYPAGE_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_마이페이지_카운트는_사용자_소유_아카이브_데이터만_집계하고_다른_사용자_데이터는_제외한다(client, make_user, make_event):
    user = make_user()
    other_user = make_user()
    event1 = make_event(title="Event 1")
    event2 = make_event(title="Event 2")

    # 저장한 행사 = UserEventStatus row count (across all statuses)
    UserEventStatus.objects.create(
        user=user, event=event1, status=UserEventStatus.Status.PLANNED
    )
    UserEventStatus.objects.create(
        user=user, event=event2, status=UserEventStatus.Status.VISITED
    )
    # 다녀온 기록
    VisitRecord.objects.create(user=user, event=event1, visited_on="2026-06-01")
    # 직접 등록
    entry = PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="개인 항목"
    )
    # 찜 목록
    EventInterest.objects.create(user=user, event=event1)
    EventInterest.objects.create(user=user, event=event2)

    # user_status_counts/user_interest_count carry no event__isnull filter —
    # a status/interest on a personal_entry (unofficial item) must count
    # toward 저장한 행사/찜 목록 too, same as an event-backed row.
    UserEventStatus.objects.create(
        user=user, personal_entry=entry, status=UserEventStatus.Status.PLANNED
    )
    EventInterest.objects.create(user=user, personal_entry=entry)

    # another user's rows must never leak into this user's counts
    UserEventStatus.objects.create(
        user=other_user, event=event1, status=UserEventStatus.Status.PLANNED
    )
    VisitRecord.objects.create(user=other_user, event=event2, visited_on="2026-06-02")
    PersonalEntry.objects.create(
        user=other_user, kind=PersonalEntry.Kind.PLACE, title="다른 유저 항목"
    )
    EventInterest.objects.create(user=other_user, event=event1)

    client.force_login(user)
    response = client.get(MYPAGE_URL)

    assert response.context["saved_count"] == 3
    assert response.context["visit_count"] == 1
    assert response.context["personal_entry_count"] == 1
    assert response.context["interest_count"] == 3


@pytest.mark.django_db
def test_아카이브_데이터가_없는_사용자의_마이페이지_카운트는_모두_0이다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(MYPAGE_URL)

    assert response.context["saved_count"] == 0
    assert response.context["visit_count"] == 0
    assert response.context["personal_entry_count"] == 0
    assert response.context["interest_count"] == 0
    assert response.context["collection_count"] == 0


@pytest.mark.django_db
def test_컬렉션_카운트는_보유_항목만_집계하고_원함_항목과_다른_사용자_항목은_제외한다(client, make_user):
    user = make_user()
    other_user = make_user()
    CollectionItem.objects.create(user=user, name="보유1", is_wanted=False)
    CollectionItem.objects.create(user=user, name="보유2", is_wanted=False)
    CollectionItem.objects.create(user=user, name="원함", is_wanted=True)
    CollectionItem.objects.create(user=other_user, name="다른 유저 항목", is_wanted=False)

    client.force_login(user)
    response = client.get(MYPAGE_URL)

    assert response.context["collection_count"] == 2


@pytest.mark.django_db
def test_스태프_사용자도_마이페이지에_접근하면_차단없이_200을_응답한다(staff_client):
    _staff, logged_in_client = staff_client()

    response = logged_in_client.get(MYPAGE_URL)

    assert response.status_code == 200
