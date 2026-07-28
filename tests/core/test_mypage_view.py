"""core.views.mypage — /mypage/ SSR page: login gate + 4-count summary context.

The 4 counts reuse archive.queries' existing aggregate functions (see
core/views.py's archive_* views for the same pattern) — this file arranges
raw archive.models rows and asserts on the rendered context/response only,
never the query layer itself (test-layer purity guard, see
tests/core/test_architecture_boundaries.py).
"""
import datetime as dt

import pytest
from django.utils import timezone

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
def test_컬렉션_카운트는_원함_전용_항목과_축_없는_항목도_포함해_전체_등록_수를_세고_다른_사용자_항목만_제외한다(
    client, make_user
):
    """collection_count is mypage's "모은 굿즈" figure (index row title "내
    컬렉션") — every item the user has registered, not merely the ones
    currently in stock. A wanted-only row (quantity=0) and a row off all
    three axes (quantity=0, is_wanted=False, tradeable_quantity=0) both
    still count, since both are registered CollectionItem rows; only another
    user's rows must be excluded (owner scope)."""
    user = make_user()
    other_user = make_user()
    CollectionItem.objects.create(user=user, name="보유1", is_wanted=False)
    CollectionItem.objects.create(user=user, name="보유2", is_wanted=False)
    CollectionItem.objects.create(user=user, name="원함", is_wanted=True, quantity=0)
    CollectionItem.objects.create(
        user=user, name="미분류행", quantity=0, is_wanted=False, tradeable_quantity=0
    )
    CollectionItem.objects.create(user=other_user, name="다른 유저 항목", is_wanted=False)

    client.force_login(user)
    response = client.get(MYPAGE_URL)

    assert response.context["collection_count"] == 4


@pytest.mark.django_db
def test_스태프_사용자도_마이페이지에_접근하면_차단없이_200을_응답한다(staff_client):
    _staff, logged_in_client = staff_client()

    response = logged_in_client.get(MYPAGE_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_비밀번호_변경_이력이_없는_사용자의_컨텍스트는_None이다(client, make_user):
    """B1"""
    user = make_user()
    client.force_login(user)

    response = client.get(MYPAGE_URL)

    assert response.context["password_changed_at"] is None


@pytest.mark.django_db
def test_가입_연도가_date_joined_연도와_일치한다(client, make_user):
    """B2"""
    user = make_user()
    client.force_login(user)

    response = client.get(MYPAGE_URL)

    assert response.context["joined_year"] == user.date_joined.year


@pytest.mark.django_db
def test_인덱스_행_수치가_각_도메인_카운트와_순서대로_일치한다(client, make_user, make_event):
    """B3: index_rows는 [내 컬렉션, 내 활동, 다녀온 기록, 직접 등록, 찜 목록] 순서.
    서로 다른 값이 되도록 각 도메인 데이터를 다르게 배치해, 행 순서가 뒤바뀌면
    이 테스트가 잡도록 한다."""
    user = make_user()
    event1 = make_event(title="Event 1")
    event2 = make_event(title="Event 2")
    event3 = make_event(title="Event 3")

    # 내 컬렉션 = 5
    for i in range(5):
        CollectionItem.objects.create(user=user, name=f"보유{i}", is_wanted=False)
    # 내 활동(저장한 행사) = 4
    UserEventStatus.objects.create(
        user=user, event=event1, status=UserEventStatus.Status.PLANNED
    )
    UserEventStatus.objects.create(
        user=user, event=event2, status=UserEventStatus.Status.PLANNED
    )
    UserEventStatus.objects.create(
        user=user, event=event3, status=UserEventStatus.Status.VISITED
    )
    entry = PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="개인 항목 1"
    )
    PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="개인 항목 2"
    )
    UserEventStatus.objects.create(
        user=user, personal_entry=entry, status=UserEventStatus.Status.PLANNED
    )
    # 다녀온 기록 = 1
    VisitRecord.objects.create(user=user, event=event1, visited_on="2026-06-01")
    # 직접 등록 = 2 (entry + 위 1건, above)
    # 찜 목록 = 3
    EventInterest.objects.create(user=user, event=event1)
    EventInterest.objects.create(user=user, event=event2)
    EventInterest.objects.create(user=user, personal_entry=entry)

    client.force_login(user)
    response = client.get(MYPAGE_URL)

    counts = [row["count"] for row in response.context["index_rows"]]
    assert counts == [
        response.context["collection_count"],
        response.context["saved_count"],
        response.context["visit_count"],
        response.context["personal_entry_count"],
        response.context["interest_count"],
    ]
    assert counts == [5, 4, 1, 2, 3]


@pytest.mark.django_db
def test_비밀번호_변경_이력_표시가_UTC가_아닌_로컬_시간대_날짜를_따른다(client, make_user):
    """password_changed_at은 UTC aware datetime으로 저장되므로, 화면 표시는
    settings.TIME_ZONE(Asia/Seoul) 기준 날짜여야 한다. UTC 23:00은 서울 기준
    다음 날 08:00이 되므로, 두 시간대의 날짜가 반드시 어긋나는 시각을 골라
    (절대 날짜를 하드코딩하지 않고 timezone.now() 기준으로 구성해) 검증한다."""
    user = make_user()
    utc_changed_at = timezone.now().astimezone(dt.timezone.utc).replace(
        hour=23, minute=0, second=0, microsecond=0
    )
    user.password_changed_at = utc_changed_at
    user.save(update_fields=["password_changed_at"])

    expected_local_date = timezone.localtime(utc_changed_at).date()
    assert expected_local_date != utc_changed_at.date()  # 시간대 경계 확인

    client.force_login(user)
    response = client.get(MYPAGE_URL)

    assert response.context["password_changed_display"] == expected_local_date.strftime(
        "%Y.%m.%d"
    )


@pytest.mark.django_db
def test_제목이_배지_라벨을_포함하는_행은_배지를_생략한다(client, make_user):
    """행 전체가 하나의 <a>라 접근 가능한 이름이 제목+배지+설명+수치로 이어
    붙는다. "내 컬렉션" 행은 제목이 배지 라벨 "컬렉션"을 부분 포함하므로
    "내 컬렉션, 컬렉션, ..."처럼 중복 낭독된다 — 이 행도 배지를 생략해야
    한다. 완전 일치("내 활동"/"내 활동")뿐 아니라 부분 포함도 규칙으로
    처리되는지 검증한다."""
    user = make_user()
    client.force_login(user)

    response = client.get(MYPAGE_URL)

    rows_by_title = {row["title"]: row for row in response.context["index_rows"]}
    assert rows_by_title["내 컬렉션"]["domain_label"] == ""
    assert rows_by_title["내 활동"]["domain_label"] == ""
    assert rows_by_title["다녀온 기록"]["domain_label"] == "내 활동"
    assert rows_by_title["직접 등록"]["domain_label"] == "내 활동"
    assert rows_by_title["찜 목록"]["domain_label"] == "내 활동"
