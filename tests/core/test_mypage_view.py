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


@pytest.mark.django_db
def test_anonymous_get_redirects_to_login(client):
    response = client.get(MYPAGE_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_authenticated_get_renders_200(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(MYPAGE_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_counts_reflect_seeded_archive_data(client, make_user, make_event):
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
def test_counts_are_zero_for_a_user_with_no_archive_data(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(MYPAGE_URL)

    assert response.context["saved_count"] == 0
    assert response.context["visit_count"] == 0
    assert response.context["personal_entry_count"] == 0
    assert response.context["interest_count"] == 0
    assert response.context["collection_count"] == 0


@pytest.mark.django_db
def test_collection_count_is_owned_items_only_owner_scoped(client, make_user):
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
def test_staff_user_also_gets_200_no_block(staff_client):
    _staff, logged_in_client = staff_client()

    response = logged_in_client.get(MYPAGE_URL)

    assert response.status_code == 200
