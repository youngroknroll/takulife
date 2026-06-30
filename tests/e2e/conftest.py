"""E2E test fixtures: Playwright + Django live_server.

These tests drive a real Chromium against a live Django server so the
JavaScript-dependent behavior (debounced live search, fragment swap, control
rebinding) is exercised end to end — the one layer the Django test-client
suite cannot cover.

live_server needs the transactional DB, so seeded data is created via a
``transactional_db``-backed fixture (not the unit suite's ``db`` factories,
which would conflict). Every E2E test is marked ``e2e`` so the fast suite can
deselect them with ``-m 'not e2e'``.
"""
import os
import types

# Playwright's sync API runs an asyncio event loop in the test thread, which
# trips Django's "SynchronousOnlyOperation" guard on ORM calls (seeding data,
# asserting persisted state). The test thread is still single-threaded and
# blocking, so allowing the sync ORM here is safe — the live_server runs in its
# own thread with its own connection. Must be set before Django ORM is touched.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

import pytest

from archive.models import PersonalEntry, UserEventStatus, VisitRecord
from events.models import Event

E2E_PASSWORD = "e2e-Pass-12345!"


def _make_event(title, **kwargs):
    return Event.objects.create(
        title=title,
        publish_status=Event.PublishStatus.PUBLISHED,
        **kwargs,
    )


@pytest.fixture
def seed(transactional_db, django_user_model):
    """Seed a regular user (with archive data) and a staff user.

    Returns a namespace: ``.user`` / ``.staff`` (User rows), ``.password``,
    and ``.events`` (the planned events, distinct titles for search).
    """
    user = django_user_model.objects.create_user(
        username="e2e_user", password=E2E_PASSWORD
    )
    staff = django_user_model.objects.create_user(
        username="e2e_staff", password=E2E_PASSWORD, is_staff=True
    )

    # Planned statuses with distinct, searchable titles for the live-search tests.
    titles = ["여름 팝업스토어", "겨울 콜라보 카페", "봄 굿즈 전시", "가을 극장 특전"]
    events = [_make_event(t, location_name="서울") for t in titles]
    for ev in events:
        UserEventStatus.objects.create(user=user, event=ev, status="planned")

    # One visit record and one personal entry so the visits/items pages render
    # real cards (and their delete/promote controls) for rebinding checks.
    VisitRecord.objects.create(
        user=user, event=events[0], visited_on="2026-06-15", short_review="좋았던 방문"
    )
    PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 검증 카페", category="카페"
    )

    return types.SimpleNamespace(
        user=user, staff=staff, password=E2E_PASSWORD, events=events
    )


def _perform_login(page, base_url, username, password):
    """Log in through the real login form and wait for the redirect away."""
    page.goto(f"{base_url}/accounts/login/?next=/archive/statuses/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{base_url}/archive/statuses/")


@pytest.fixture
def login():
    """Expose the login helper as a fixture (tests/e2e is not an import package,
    so a relative import would fail — inject it instead)."""
    return _perform_login
