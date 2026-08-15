"""events.services의 방어적 오류 처리 분기를 검증한다.

- create_published_event: 사전 검사를 통과한 뒤에도 경합으로 발생하는
  무결성 오류(TOCTOU)를 DuplicateOfficialUrlError로 변환한다.
"""
import pytest
from django.db import IntegrityError

from events.services import (
    DuplicateOfficialUrlError,
    create_published_event,
)
from events.models import Event

pytestmark = pytest.mark.domain


@pytest.mark.django_db
class TestCreatePublishedEventRace:
    def test_생성_경합으로_무결성_오류가_발생하면_공식_URL_중복_예외로_변환된다(self, monkeypatch):
        # 사전 검사는 통과하지만 실제 INSERT가 경합으로 실패해
        # DuplicateOfficialUrlError로 변환되는지 확인한다.
        def boom(*args, **kwargs):
            raise IntegrityError("duplicate key")

        monkeypatch.setattr(Event.objects, "create", boom)

        with pytest.raises(DuplicateOfficialUrlError):
            create_published_event(
                title="경합 행사", official_url="https://race.example.com/"
            )
