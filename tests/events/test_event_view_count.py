"""행사 상세 페이지의 조회수 집계를 검증한다.

다루는 범위:
- 새 Event의 view_count 기본값은 0이다.
- GET /events/<id>/를 두 번 호출하면 DB의 view_count가 2로 늘어난다.
- GET /events/<draft_id>/는 404를 반환하고 view_count를 늘리지 않는다.
"""
import pytest
from django.test import Client

from events.models import Event


@pytest.mark.django_db
class TestViewCountDefault:
    pytestmark = pytest.mark.domain

    def test_새로_생성된_행사의_조회수는_0이다(self, make_event):
        event = make_event()
        assert event.view_count == 0


@pytest.mark.django_db
class TestViewCountIncrement:
    pytestmark = pytest.mark.web

    def test_행사_상세를_두_번_조회하면_조회수가_2로_증가한다(self, make_event):
        event = make_event()
        client = Client()

        client.get(f"/events/{event.pk}/")
        client.get(f"/events/{event.pk}/")

        event.refresh_from_db()
        assert event.view_count == 2

    def test_미게시_행사_상세_조회는_404를_반환하고_조회수를_증가시키지_않는다(self, make_event):
        event = make_event(publish_status=Event.PublishStatus.DRAFT)
        client = Client()

        resp = client.get(f"/events/{event.pk}/")

        assert resp.status_code == 404
        event.refresh_from_db()
        assert event.view_count == 0
