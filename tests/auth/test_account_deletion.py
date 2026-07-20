"""Account deletion request (accounts.views.delete_account).

GET /accounts/delete/ renders a password-reconfirm form (login required).
POST verifies the current password, then records a 10-day grace-period
deletion request via accounts.services.request_deletion (see
.docs/plans/2026-07-20-deletion-grace-period-plan.md) — the account itself
is not deleted here. The eventual hard delete, and the archive data/media
cascade it triggers (see archive/models.py, archive/signals.py), happen in
accounts.services.execute_pending_deletions and are verified in
tests/auth/test_account_deletion_purge.py, not this file.
"""
import logging
import time as real_time
from datetime import datetime, timedelta, timezone as dt_timezone

import django.core.cache.backends.base as cache_base
import django.core.cache.backends.db as cache_db
import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

import accounts.views as accounts_views
from accounts import services
from accounts.models import User
from accounts.signals import cancel_pending_deletion_on_login
from accounts.views import _delete_attempts_cache_key

DELETE_URL = "/accounts/delete/"


class _FakeClock:
    """A controllable stand-in for the `time` module.

    Swapped into the two cache-backend modules only (not the process-wide
    `time` module, which sessions/logging/etc. also rely on) so fast-forwarding
    the lockout window cannot leak into anything else the request cycle
    depends on.
    """

    def __init__(self, start):
        self._now = start

    def time(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


@pytest.fixture
def cache_clock(monkeypatch):
    """Lets a test fast-forward the cache backend's notion of "now" without
    sleeping.

    PR-0e switched the default cache backend from LocMemCache to
    DatabaseCache (config/settings.py CACHES), which reads "now" from two
    independent places: `BaseCache.get_backend_timeout` (base.py) computes
    the expiry as a raw `time.time() + timeout` epoch offset, while
    `DatabaseCache.get`/`_base_set` (db.py) compares that expiry against
    `django.utils.timezone.now()` — imported there as `from
    django.utils.timezone import now as tz_now`, which binds the function
    object into db.py's own namespace at import time. Patching
    `django.utils.timezone.now` itself would not reach db.py's already-bound
    `tz_now` reference, so both the `base.py` `time` module reference and
    db.py's `tz_now` name are patched here, each to read off the same fake
    clock, so expiry-setting and expiry-checking stay consistent under a
    fast-forward.

    accounts.views's own fixed-window lockout (_is_delete_locked /
    _register_failed_delete_attempt) also reads `time.time()` directly (it
    stores its own deadline rather than trusting the cache backend's TTL —
    see accounts/views.py), so that module's `time` reference is patched too.
    """
    clock = _FakeClock(real_time.time())
    monkeypatch.setattr(cache_base, "time", clock)
    monkeypatch.setattr(
        cache_db,
        "tz_now",
        lambda: datetime.fromtimestamp(
            clock.time(), tz=dt_timezone.utc if settings.USE_TZ else None
        ),
    )
    monkeypatch.setattr(accounts_views, "time", clock)
    return clock


@pytest.mark.django_db
@pytest.mark.web
def test_비로그인_사용자가_계정_삭제_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get(DELETE_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
@pytest.mark.web
def test_스태프가_계정_삭제_페이지에_접근하면_403으로_거부된다(client, make_user, valid_password):
    """Self-deletion is UI-hidden for staff (no header link, per §account
    menu spec), but the view must also enforce it server-side — a staff
    account is removed via Django admin only, never self-service."""
    staff = make_user(password=valid_password, is_staff=True)
    client.force_login(staff)

    response = client.get(DELETE_URL)

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.web
def test_스태프의_계정_삭제_요청은_403으로_거부되고_계정이_유지된다(client, make_user, valid_password):
    staff = make_user(password=valid_password, is_staff=True)
    client.force_login(staff)

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 403
    assert User.objects.filter(pk=staff.pk).exists()


@pytest.mark.django_db
@pytest.mark.web
def test_스태프의_잘못된_비밀번호_요청은_잠금_카운터를_증가시키지_않는다(
    client, make_user, valid_password
):
    """Regression guard for check ordering: the is_staff guard must run
    *before* the lockout counter, or a staff account (already blocked by
    role) would still burn through _register_failed_delete_attempt on every
    repeated POST — a pointless side effect for a request that was always
    going to be rejected."""
    staff = make_user(password=valid_password, is_staff=True)
    client.force_login(staff)

    for _ in range(5):
        response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert response.status_code == 403

    assert cache.get(_delete_attempts_cache_key(staff)) is None


@pytest.mark.django_db
@pytest.mark.web
def test_로그인_사용자가_계정_삭제_페이지에_접근하면_확인_폼이_렌더링된다(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.get(DELETE_URL)

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.web
def test_잘못된_비밀번호로_계정_삭제를_요청하면_계정이_삭제되지_않는다(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.post(DELETE_URL, {"password": "definitely-wrong"})

    assert response.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
@pytest.mark.slow
def test_다섯_번_잘못된_비밀번호_시도_후에는_올바른_비밀번호도_잠긴다(
    client, make_user, valid_password
):
    """A session-riding attacker cannot brute-force the password check
    indefinitely: after 5 failures, the 6th POST is rejected without even
    checking the (correct) password, and the account survives."""
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert response.status_code == 200

    locked_response = client.post(DELETE_URL, {"password": valid_password})

    assert locked_response.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
@pytest.mark.slow
def test_다섯_번_잘못된_비밀번호_시도_시_잠금_경고가_사용자와_횟수를_포함해_정확히_1회_기록된다(
    client, make_user, valid_password, caplog
):
    """The lockout WARNING is the only observable signal a hijacked-session
    brute-force attempt leaves behind (LOG-01/LOG-02,
    .docs/plans/2026-07-19-logging-coverage-plan.md §4): it must fire exactly
    once at the moment the budget is exhausted, carry the user's pk and the
    attempt count, and never leak the password, session key, or client IP —
    further failed attempts while already locked must not add more
    warnings."""
    caplog.set_level(logging.WARNING, logger="accounts.views")
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert response.status_code == 200

    warnings = [record for record in caplog.records if record.name == "accounts.views"]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert str(user.pk) in message
    assert "5" in message
    assert "definitely-wrong" not in message
    session_key = client.session.session_key
    assert session_key is not None
    assert session_key not in message
    assert "127.0.0.1" not in message

    for _ in range(3):
        locked_response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert locked_response.status_code == 200

    warnings_after_lockout = [
        record for record in caplog.records if record.name == "accounts.views"
    ]
    assert len(warnings_after_lockout) == 1


@pytest.mark.django_db
@pytest.mark.slow
def test_잠금_상태에서_요청하면_잠시_후_다시_시도하라는_오류가_표시된다(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        client.post(DELETE_URL, {"password": "definitely-wrong"})

    locked_response = client.post(DELETE_URL, {"password": valid_password})

    body = locked_response.content.decode("utf-8", "ignore")
    assert "잠시 후 다시 시도" in body


@pytest.mark.django_db
@pytest.mark.slow
def test_잠금_후_15분이_지나면_올바른_비밀번호로_다시_탈퇴를_예약할_수_있다(
    client, make_user, valid_password, cache_clock
):
    """The lockout is a *fixed* 15-minute window, not a permanent block —
    once it elapses, the correct password reserves the deletion again (see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md DEL-10)."""
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        client.post(DELETE_URL, {"password": "definitely-wrong"})
    still_locked = client.post(DELETE_URL, {"password": valid_password})
    assert still_locked.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()

    cache_clock.advance(60 * 15 + 1)  # just past the 15-minute window

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.slow
def test_잠금_창은_이후_실패로_연장되지_않고_최초_실패_시점_기준으로_고정된다(
    client, make_user, valid_password, cache_clock
):
    """Regression guard for the fixed-window design: if `cache.add` +
    `incr` were ever swapped for a `cache.get`/`cache.set` pattern that
    refreshes the TTL on every write, each new failure would push the
    lockout window out again and repeated failures could keep the account
    locked indefinitely.

    Spreads 5 failures so the last 4 land near the end of the *original*
    window, then jumps just past that original window's end (before any
    TTL-refreshed window would have expired) and confirms the correct
    password already works — proving later failures did not extend the
    window set by the first one.
    """
    user = make_user(password=valid_password)
    client.force_login(user)

    client.post(DELETE_URL, {"password": "definitely-wrong"})  # failure 1, t=0

    cache_clock.advance(60 * 14 + 50)  # near the end of the original window
    for _ in range(4):  # failures 2-5; a sliding window would refresh here
        client.post(DELETE_URL, {"password": "definitely-wrong"})
    still_locked = client.post(DELETE_URL, {"password": valid_password})
    assert still_locked.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()

    cache_clock.advance(20)  # now just past the *original* 15-minute window

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.slow
def test_다섯_번_미만_실패_후_올바른_비밀번호는_탈퇴를_예약한다(
    client, make_user, valid_password
):
    """Below the lockout threshold, a subsequent correct password still
    works — the failure counter must not accumulate across separate
    deletion sessions once the password check succeeds."""
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(3):
        response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert response.status_code == 200

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.slow
def test_한_사용자의_잠금은_다른_사용자의_계정_탈퇴_예약을_막지_않는다(client, make_user, valid_password):
    """One user's exhausted attempt budget must not lock out another user."""
    attacker = make_user(password=valid_password)
    victim = make_user(password=valid_password)

    client.force_login(attacker)
    for _ in range(5):
        client.post(DELETE_URL, {"password": "definitely-wrong"})
    locked_response = client.post(DELETE_URL, {"password": valid_password})
    assert locked_response.status_code == 200
    assert User.objects.filter(pk=attacker.pk).exists()

    client.force_login(victim)
    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=victim.pk).exists()
    victim.refresh_from_db()
    assert victim.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.web
def test_계정_삭제_직후_기존_세션으로는_보호된_페이지에_접근할_수_없다(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    client.post(DELETE_URL, {"password": valid_password})

    # The browser still holds the old session cookie, but the session was
    # flushed server-side — a protected page must bounce to login.
    response = client.get("/archive/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
@pytest.mark.web
def test_삭제된_계정으로는_다시_로그인할_수_없다(client, make_user, valid_password):
    """DEL-11: the deletion-request POST alone no longer removes the
    account (10-day grace period) — this test now drives the account past
    the grace period via execute_pending_deletions before attempting the
    login, so the originally-protected "a purged account cannot log back
    in" behavior stays covered under the new policy (see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md)."""
    user = make_user(email="leaving@example.com", password=valid_password)
    client.force_login(user)
    client.post(DELETE_URL, {"password": valid_password})
    User.objects.filter(pk=user.pk).update(
        deletion_requested_at=timezone.now() - timedelta(days=10, hours=1)
    )
    services.execute_pending_deletions()

    login_response = client.post(
        "/accounts/login/",
        {"login": "leaving@example.com", "password": valid_password},
    )

    assert login_response.status_code == 200  # form re-rendered, not authenticated
    archive_response = client.get("/archive/")
    assert archive_response.status_code == 302
    assert "/accounts/login/" in archive_response["Location"]


@pytest.mark.django_db
@pytest.mark.web
def test_올바른_비밀번호로_탈퇴를_요청하면_계정은_유지되고_삭제_예약_시각이_기록된다(
    client, make_user, valid_password
):
    """DEL-01 (10-day grace period): a correct-password deletion request no
    longer hard-deletes the account immediately — it must survive, and the
    request is recorded as a pending deletion via `deletion_requested_at`
    (see .docs/plans/2026-07-20-deletion-grace-period-plan.md)."""
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.web
def test_탈퇴를_요청하면_다른_기기의_세션도_함께_종료된다(client, make_user, valid_password):
    """DEL-02 (10-day grace period): a hijacked or simply forgotten second
    device's session must not survive the owner's deletion request for the
    remaining 10 days — every session belonging to the user is invalidated,
    not just the one that submitted the request (see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md)."""
    user = make_user(password=valid_password)
    client_a = client
    client_b = Client()
    client_a.force_login(user)
    client_b.force_login(user)

    response = client_a.post(DELETE_URL, {"password": valid_password})
    assert response.status_code == 302

    other_device_response = client_b.get("/archive/")

    assert other_device_response.status_code == 302
    assert "/accounts/login/" in other_device_response["Location"]


@pytest.mark.django_db
@pytest.mark.web
def test_유예_기간_중_다시_로그인하면_탈퇴_예약이_취소되고_안내_메시지가_표시된다(
    client, make_verified_user, valid_password
):
    """DEL-03: logging back in during the 10-day grace period is itself the
    cancellation — no extra confirmation step is needed, because a
    successful login is already re-authentication (see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md). The pending
    request is set up explicitly here via accounts.services.request_deletion
    rather than hidden behind a dedicated fixture, so the precondition stays
    visible in the test body."""
    user = make_verified_user()
    services.request_deletion(user)
    assert user.deletion_requested_at is not None

    response = client.post(
        "/accounts/login/",
        {"login": user.email, "password": valid_password},
        follow=True,
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.deletion_requested_at is None
    messages_text = " ".join(str(message) for message in response.context["messages"])
    assert "취소" in messages_text


@pytest.mark.django_db
@pytest.mark.web
def test_삭제_예약이_없는_사용자가_로그인하면_아무_안내도_표시되지_않는다(
    client, make_verified_user, valid_password
):
    """DEL-04: an ordinary login (no pending deletion) must stay a no-op —
    `cancel_deletion`'s rowcount is 0, so the login-cancels-deletion signal
    must not surface a cancellation message that never happened (see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md)."""
    user = make_verified_user()
    assert user.deletion_requested_at is None

    response = client.post(
        "/accounts/login/",
        {"login": user.email, "password": valid_password},
        follow=True,
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.deletion_requested_at is None
    messages_text = " ".join(str(message) for message in response.context["messages"])
    assert "취소" not in messages_text


@pytest.mark.django_db
@pytest.mark.web
def test_로그인_시그널이_발화하면_로그인_경로와_무관하게_탈퇴_예약이_취소된다(make_verified_user):
    """DEL-05: the receiver's own contract is path-independent and
    request-optional cancellation, exercised here by calling
    `cancel_pending_deletion_on_login` directly instead of sending
    `user_logged_in` (django-axes' own receiver on that signal requires a
    real `request` and raises AttributeError on `request=None` — an
    environment quirk unrelated to our receiver, not something under test
    here). The signal *wiring* itself is already proven by DEL-03's web
    login path. `request=None` exercises the no-request guard: no messages
    backend is available, so the receiver must skip the notification rather
    than raise (see .docs/plans/2026-07-20-deletion-grace-period-plan.md)."""
    user = make_verified_user()
    services.request_deletion(user)
    assert user.deletion_requested_at is not None

    cancel_pending_deletion_on_login(sender=type(user), request=None, user=user)

    user.refresh_from_db()
    assert user.deletion_requested_at is None
