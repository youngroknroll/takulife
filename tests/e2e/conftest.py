"""여정 기반 e2e 전용 픽스처 — 실제 Chromium + Django live_server.

이 계층은 로그인 게이트·JS fetch처럼 Django 테스트 클라이언트가 못 잡는
여정만 다룬다(기본 `uv run pytest -q`에서는 제외). `login_as`가
`RequestFactory` + `django.contrib.auth.login()`을 쓰는 이유는 로그인
뷰(레이트리밋 대상)를 거치지 않으면서도 `user_logged_in` 시그널은 실제
로그인과 같게 발화시키기 위해서다.
"""
import secrets
from importlib import import_module

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import login
from django.core.cache import cache
from django.db.utils import Error as DjangoDatabaseError
from django.test import RequestFactory

from drafts.models import EventDraft
from events.models import Event

E2E_PASSWORD = "e2e-Pass-12345!"


@pytest.fixture(scope="session", autouse=True)
def allow_async_unsafe_for_playwright():
    """Playwright sync API가 테스트 스레드에서 asyncio 이벤트 루프를 돌려
    Django의 ORM 동기 가드에 걸린다 — tests/e2e 안에서만 풀고 끝나면 되돌린다.
    """
    import os

    had_previous = "DJANGO_ALLOW_ASYNC_UNSAFE" in os.environ
    previous = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"
    yield
    if had_previous:
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = previous
    else:
        os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "tests/e2e/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server.url


@pytest.fixture
def page(page):
    page.set_default_timeout(10_000)
    return page


@pytest.fixture
def verified_user(transactional_db, django_user_model):
    def _make(email=None, *, password=None, is_staff=False):
        email = email or f"e2e_{secrets.token_hex(4)}@example.com"
        user = django_user_model.objects.create_user(
            email=email, password=password, is_staff=is_staff
        )
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        return user

    return _make


@pytest.fixture
def login_as(live_server, context):
    """로그인 뷰(레이트리밋 대상)를 거치지 않고 세션 쿠키를 심는다.

    axes·`accounts/signals.py`의 `cancel_pending_deletion_on_login`은 모두
    `user_logged_in` 시그널로 동작하므로, 이 경로도 `django.contrib.auth.
    login()`을 실제로 호출해 그 시그널을 발화시킨다. 주의: axes의 수신자가
    `request.META`를 읽으므로 `RequestFactory` 기본 META(REMOTE_ADDR=
    127.0.0.1)로 충분해야 한다 — 실제 실행은 오케스트레이터가 확인한다.
    """
    def _login(user):
        request = RequestFactory().get("/")
        request.session = import_module(settings.SESSION_ENGINE).SessionStore()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.save()
        context.add_cookies(
            [
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": request.session.session_key,
                    "url": live_server.url,
                }
            ]
        )

    return _login


@pytest.fixture
def clear_cache_e2e(transactional_db):
    cache.clear()
    yield
    try:
        cache.clear()
    except DjangoDatabaseError:
        pass


@pytest.fixture
def make_published_event(transactional_db):
    def _make(title, **kwargs):
        return Event.objects.create(
            title=title, publish_status=Event.PublishStatus.PUBLISHED, **kwargs
        )

    return _make


@pytest.fixture
def make_pending_draft(transactional_db):
    def _make(**kwargs):
        defaults = {
            "source_url": f"https://example.com/drafts/{secrets.token_hex(4)}",
            "raw_title": "e2e 드래프트",
            "extracted_title": "e2e 드래프트",
            "extracted_category": "popup_store",
            "extracted_region": "seoul",
            "review_status": EventDraft.ReviewStatus.PENDING,
        }
        return EventDraft.objects.create(**{**defaults, **kwargs})

    return _make
