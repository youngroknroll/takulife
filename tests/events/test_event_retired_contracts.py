"""폐기된 행사 API 경로가 더 이상 응답하지 않는지 확인하는 계약 테스트."""

import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_스태프가_폐기된_포스터_경로에_요청하면_찾을_수_없다(staff_client, make_event):
    _, client = staff_client()
    event = make_event()

    response = client.delete(f"/api/events/{event.pk}/poster/")

    assert response.status_code == 404
