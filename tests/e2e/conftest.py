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

from allauth.account.models import EmailAddress
from archive.models import PersonalEntry, UserEventStatus, VisitRecord
from django.core.cache import cache
from django.db.utils import Error as DjangoDatabaseError
from events.models import Event

E2E_PASSWORD = "e2e-Pass-12345!"


@pytest.fixture(autouse=True)
def _clear_cache_between_e2e_tests(transactional_db):
    """Clear the shared cache before and after every e2e test.

    This is not a reinstatement of the "promote everything to DB access"
    autouse pattern the 2026-07-17 speed track removed from
    tests/conftest.py — it is isolation for the one layer where a
    transaction rollback cannot undo a cache write. Two facts combine to
    make that leak observable only here:

    1. The shared cache table (``core/migrations/0002_create_shared_cache_
       table.py``, ``createcachetable``) has no Django model, so
       pytest-django's ``transactional_db`` TRUNCATE-based flush — which
       only knows about migrated *model* tables — never touches it. A
       normal (non-e2e) ``@pytest.mark.django_db`` test's cache writes are
       undone for free because they happen inside that test's own rolled-
       back transaction; live_server requests run through a real HTTP
       connection outside that transaction, so nothing rolls them back.
    2. allauth merges its own rate-limit defaults under the project's
       ``ACCOUNT_RATE_LIMITS`` (django-allauth ``app_settings.RATE_LIMITS``:
       ``ret.update(rls)``), and config/settings.py never overrides the
       default ``"login": "30/m/ip"`` — which counts every login attempt,
       *including successes*. A full e2e run performs far more than 30 real
       logins inside a minute, so without a clear the counter accumulates
       across tests and a later test's login attempt gets silently 302'd
       back to the form as a 429 — which ``_perform_login``'s
       ``wait_for_url`` then times out on (TS-INF-04).

    Depends on ``transactional_db`` rather than the root conftest's
    ``db``-backed ``clear_cache``: every e2e test already depends on
    ``live_server`` (directly, or via the ``seed`` fixture, itself
    ``transactional_db``-backed), and pytest-django's ``db`` and
    ``transactional_db`` fixtures are mutually exclusive — reusing the root
    fixture here would conflict. ``ACCOUNT_RATE_LIMITS`` itself is untouched
    (production security setting); this only clears the counter, it does
    not loosen the limit.
    """
    cache.clear()
    yield
    try:
        cache.clear()
    except DjangoDatabaseError:
        pass


def _verified_user(django_user_model, email, **kwargs):
    """Create a user with a pre-verified primary email.

    ACCOUNT_EMAIL_VERIFICATION=mandatory blocks login for unverified
    accounts, so E2E-seeded users need a verified EmailAddress row up
    front — there's no confirmation email to click in a live_server test.
    """
    user = django_user_model.objects.create_user(email=email, password=E2E_PASSWORD, **kwargs)
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


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
    user = _verified_user(django_user_model, "e2e_user@example.com")
    staff = _verified_user(django_user_model, "e2e_staff@example.com", is_staff=True)

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


def _perform_login(page, base_url, email, password):
    """Log in through the real login form and wait for the redirect away."""
    page.goto(f"{base_url}/accounts/login/?next=/archive/statuses/")
    page.fill('input[name="login"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url(f"{base_url}/archive/statuses/")


@pytest.fixture
def login():
    """Expose the login helper as a fixture (tests/e2e is not an import package,
    so a relative import would fail — inject it instead)."""
    return _perform_login
