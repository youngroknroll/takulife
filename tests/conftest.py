"""Shared pytest fixtures: loosely-coupled object factories.

Each factory is a callable returned by a fixture, so call sites pass their own
overrides (title, username, password, …) and keep their exact inputs — no rigid
shared object that would change what a test exercises.
"""
import io
import secrets

import PIL.Image
import pytest

from events.models import Event


@pytest.fixture
def make_event(db):
    def _make(**kwargs):
        defaults = {"title": "Test Event", "publish_status": Event.PublishStatus.PUBLISHED}
        return Event.objects.create(**{**defaults, **kwargs})

    return _make


@pytest.fixture
def make_draft_event(make_event):
    def _make(**kwargs):
        return make_event(**{"publish_status": Event.PublishStatus.DRAFT, **kwargs})

    return _make


@pytest.fixture
def make_user(db, django_user_model):
    def _make(username=None, password=None, **kwargs):
        username = username or f"user_{secrets.token_hex(4)}"
        # Strong by default so registration-validator paths pass; callers that
        # care about the exact password pass their own.
        password = password or "Aa1!" + secrets.token_urlsafe(16)
        return django_user_model.objects.create_user(
            username=username, password=password, **kwargs
        )

    return _make


@pytest.fixture
def png_bytes():
    def _make(width=10, height=10, color=(255, 0, 0)):
        buf = io.BytesIO()
        PIL.Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
        return buf.getvalue()

    return _make
