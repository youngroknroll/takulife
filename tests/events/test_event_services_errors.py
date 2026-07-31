"""events.services의 방어적 오류 처리 분기를 검증한다.

- create_published_event: 사전 검사를 통과한 뒤에도 경합으로 발생하는
  무결성 오류(TOCTOU)를 DuplicateOfficialUrlError로 변환한다.
- set_event_poster: 기존 파일 정리가 실패해도 예외를 전파하지 않고
  로그만 남긴 뒤 업로드를 그대로 진행한다.
"""
import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError

import events.services as services
from events.services import (
    DuplicateOfficialUrlError,
    create_published_event,
    set_event_poster,
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


@pytest.mark.django_db
class TestSetEventPosterCleanupFailure:
    def test_기존_포스터_삭제가_실패해도_새_포스터_업로드는_성공한다(self, make_event, png_bytes, monkeypatch):
        event = make_event(title="포스터 교체")
        event.poster_image.save("old.png", ContentFile(png_bytes()), save=True)

        # 기존 파일 정리가 실패하도록 만든다; set_event_poster는 로그만 남기고 계속돼야 한다.
        def raising_delete(self, name):
            raise OSError("storage delete failed")

        monkeypatch.setattr(FileSystemStorage, "delete", raising_delete)

        set_event_poster(event=event, image=ContentFile(png_bytes(), name="new.png"))

        event.refresh_from_db()
        assert event.poster_image
