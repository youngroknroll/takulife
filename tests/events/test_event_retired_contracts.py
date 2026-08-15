"""폐기된 행사 API 경로와 필드가 더 이상 응답·존재하지 않는지 확인하는 계약 테스트."""

import pytest

from events.models import Event

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_스태프가_폐기된_포스터_경로에_요청하면_찾을_수_없다(staff_client, make_event):
    _, client = staff_client()
    event = make_event()

    response = client.delete(f"/api/events/{event.pk}/poster/")

    assert response.status_code == 404


@pytest.mark.contract
def test_행사_모델은_포스터_필드를_제공하지_않는다():
    assert "poster_image" not in {field.name for field in Event._meta.get_fields()}
