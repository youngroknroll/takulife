"""스태프 대시보드 실시간 수집 현황 조회 API 계약."""
import pytest

pytestmark = pytest.mark.web

LIVE_URL = "/staff/api/discovery/live/"


@pytest.mark.django_db
@pytest.mark.parametrize("login_as_regular_user", [False, True], ids=["익명", "비스태프"])
def test_관리자가_아니면_수집_실시간_현황을_조회할_수_없다(client, make_user, login_as_regular_user):
    if login_as_regular_user:
        client.force_login(make_user())

    response = client.get(LIVE_URL)

    assert response.status_code == 403
