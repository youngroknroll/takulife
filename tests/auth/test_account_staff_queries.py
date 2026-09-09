"""accounts.queries.list_accounts_for_staff — 스태프 계정 콘솔 목록 조회
계약(트랙 19 H1, T2-S2·S3). HTTP 관문·페이지네이션은
tests/staff/test_staff_account_views.py가 다루고, 여기는 조회 함수
자체의 필드·정렬·검색 계약만 본다.
"""
import datetime

import pytest
from django.utils import timezone

from accounts.models import User
from accounts.queries import list_accounts_for_staff

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_list_accounts_for_staff는_필요한_필드만_최신_가입순으로_반환한다(make_user):
    older = make_user(email="older-account@example.com")
    newer = make_user(email="newer-account@example.com")
    # 생성 순서만으로는 date_joined 차이가 미미해 정렬을 못 미덥게 만들 수
    # 있어, older 쪽을 명시적으로 과거로 되돌린다.
    User.objects.filter(pk=older.pk).update(
        date_joined=timezone.now() - datetime.timedelta(days=1)
    )

    rows = list(list_accounts_for_staff())

    assert [row["id"] for row in rows if row["id"] in (older.pk, newer.pk)] == [
        newer.pk,
        older.pk,
    ]
    expected_keys = {
        "id",
        "email",
        "date_joined",
        "last_login",
        "is_staff",
        "is_superuser",
        "is_active",
        "deletion_requested_at",
    }
    assert set(rows[0].keys()) == expected_keys


@pytest.mark.django_db
def test_list_accounts_for_staff는_검색어와_이메일이_부분_일치하는_사용자만_반환한다(make_user):
    make_user(email="unrelated-account@example.com")
    target = make_user(email="beta-search-match@example.com")

    rows = list(list_accounts_for_staff(search="search-match"))

    assert [row["id"] for row in rows] == [target.pk]
