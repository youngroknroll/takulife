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


@pytest.mark.django_db
class TestCreatePublishedEventRace:
    def test_integrity_error_maps_to_duplicate(self, monkeypatch):
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
    def test_old_poster_delete_failure_is_swallowed(self, make_event, png_bytes, monkeypatch):
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
