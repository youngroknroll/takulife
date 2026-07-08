"""Shared pytest fixtures: loosely-coupled object factories.

Each factory is a callable returned by a fixture, so call sites pass their own
overrides (title, username, password, …) and keep their exact inputs — no rigid
shared object that would change what a test exercises.
"""
import io
import secrets

import PIL.Image
import pytest
from django.core.cache import cache
from django.test import Client

from events.models import Event


@pytest.fixture(autouse=True)
def clear_cache():
    """Isolate DRF throttle state between tests.

    Scoped rate throttling stores request history in the default (LocMem) cache,
    which is not rolled back with the DB. Clear it around every test so one
    test's promotion requests never count against another's throttle budget.
    """
    cache.clear()
    yield
    cache.clear()


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
    def _make(email=None, password=None, **kwargs):
        email = email or f"user_{secrets.token_hex(4)}@example.com"
        # Strong by default so registration-validator paths pass; callers that
        # care about the exact password pass their own.
        password = password or "Aa1!" + secrets.token_urlsafe(16)
        return django_user_model.objects.create_user(
            email=email, password=password, **kwargs
        )

    return _make


@pytest.fixture
def user_client(make_user):
    """(user, force_login된 Client) 팩토리 — 파일마다 복제되던 _login 헬퍼를 대체."""
    def _make(user=None, **user_kwargs):
        user = user or make_user(**user_kwargs)
        client = Client()
        client.force_login(user)
        return user, client

    return _make


@pytest.fixture
def staff_client(user_client):
    """(staff_user, force_login된 Client) 팩토리. is_superuser 등은 kwargs로 통과."""
    def _make(**user_kwargs):
        return user_client(is_staff=True, **user_kwargs)

    return _make


@pytest.fixture
def png_bytes():
    def _make(width=10, height=10, color=(255, 0, 0)):
        buf = io.BytesIO()
        PIL.Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
        return buf.getvalue()

    return _make
