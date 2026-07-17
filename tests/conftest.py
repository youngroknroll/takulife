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
from django.db.utils import Error as DjangoDatabaseError
from django.test import Client

from drafts.models import DraftSource, EventDraft
from events.models import Event


@pytest.fixture
def clear_cache(db):
    """Isolate DRF throttle / rate-limit state between tests — request it
    explicitly in tests that read or assert on cache-backed counters.

    Not autouse (2026-07-17 speed track): the cache backend is DatabaseCache
    (config/settings.py CACHES), and a `@pytest.mark.django_db` test's own
    transaction already rolls back any cache writes it makes — so most
    cache/throttle tests are isolated for free and never needed an explicit
    clear. Request this fixture only when a test's own setup (not the
    previous test's teardown) needs a guaranteed-empty cache, e.g. because it
    reads a cache key before writing to it.

    Depends on the `db` fixture: cache.clear() itself needs a DB
    connection/transaction, since the cache table lives in Postgres.

    The teardown clear is wrapped: a test that intentionally simulates a DB
    outage (e.g. tests/core/test_api_bootstrap.py's
    test_health_endpoint_returns_503_when_database_unreachable, which
    monkeypatches connection.ensure_connection to always raise) leaves that
    monkeypatch in effect for this fixture's post-yield teardown too — clear
    is best-effort cache hygiene, not the behavior under test, so a DB error
    here must not turn an intentional-outage test into a spurious failure.
    """
    cache.clear()
    yield
    try:
        cache.clear()
    except DjangoDatabaseError:
        pass


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
        # No password requested: create_user(password=None) makes an
        # unusable-password user (Django's make_password(None) contract) —
        # cheaper than a real hash and correct for tests that never log the
        # user in with a password (e.g. force_login). Callers that do need a
        # working password (login/registration paths) pass their own.
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


@pytest.fixture
def make_draft(db):
    def _make(source_url=None, **kwargs):
        # source_url is unique — synthesize one so bare calls never collide.
        # `is None` (not truthy-check) so an intentional "" is preserved.
        if source_url is None:
            source_url = f"https://example.com/{secrets.token_hex(4)}"
        return EventDraft.objects.create(source_url=source_url, **kwargs)

    return _make


@pytest.fixture
def make_source(db):
    def _make(**overrides):
        defaults = {
            "name": "Test Source",
            "url": "https://example.com/feed.xml",
            "source_type": DraftSource.SourceType.RSS,
            "enabled": True,
        }
        return DraftSource.objects.create(**{**defaults, **overrides})

    return _make


@pytest.fixture
def fail_if_called():
    """A collaborator stand-in that fails the test if it's ever invoked —
    for asserting a code path is skipped entirely (monkeypatch target)."""
    def _fn(*args, **kwargs):
        raise AssertionError("this collaborator must not be called")

    return _fn
