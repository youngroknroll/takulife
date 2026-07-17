"""Tests for the defensive error branches in events.services.

- create_published_event maps a unique-constraint IntegrityError (the TOCTOU
  race past the pre-check) onto DuplicateOfficialUrlError.
- set_event_poster swallows-and-logs a storage cleanup failure instead of
  propagating it (the upload always wins).
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
        # Pre-check passes (no existing row), but the INSERT races and fails with
        # IntegrityError → mapped to DuplicateOfficialUrlError.
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

        # Make the old-file cleanup raise; set_event_poster must log and continue.
        def raising_delete(self, name):
            raise OSError("storage delete failed")

        monkeypatch.setattr(FileSystemStorage, "delete", raising_delete)

        # Should NOT raise despite the cleanup failure.
        set_event_poster(event=event, image=ContentFile(png_bytes(), name="new.png"))

        event.refresh_from_db()
        assert event.poster_image  # new poster assigned, upload won
