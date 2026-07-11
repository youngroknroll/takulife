"""Account deletion (accounts.views.delete_account).

GET /accounts/delete/ renders a password-reconfirm form (login required).
POST verifies the current password before deleting the account; owned
archive data and media files cascade via existing FK on_delete/signals
wiring (see archive/models.py, archive/signals.py) — this view does not
re-implement that cleanup, it only orchestrates the password check, the
delete, and ending the session.
"""
import time as real_time

import django.core.cache.backends.base as cache_base
import django.core.cache.backends.locmem as cache_locmem
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from archive.models import PersonalEntry, VisitRecord, VisitRecordPhoto

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
    """Lets a test fast-forward LocMemCache's notion of "now" without
    sleeping. `django.core.cache.backends.{locmem,base}` each do a bare
    `import time` and call `time.time()`; replacing the `time` name in only
    those two modules' namespaces controls cache expiry math without
    touching the real `time` module everything else in the process uses."""
    clock = _FakeClock(real_time.time())
    monkeypatch.setattr(cache_locmem, "time", clock)
    monkeypatch.setattr(cache_base, "time", clock)
    return clock


@pytest.mark.django_db
def test_anonymous_get_redirects_to_login(client):
    response = client.get(DELETE_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_authenticated_get_renders_confirm_form(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.get(DELETE_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_wrong_password_does_not_delete_the_account(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.post(DELETE_URL, {"password": "definitely-wrong"})

    assert response.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_five_wrong_passwords_lock_out_even_the_correct_password(
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
def test_lockout_shows_a_try_again_later_error(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        client.post(DELETE_URL, {"password": "definitely-wrong"})

    locked_response = client.post(DELETE_URL, {"password": valid_password})

    body = locked_response.content.decode("utf-8", "ignore")
    assert "잠시 후 다시 시도" in body


@pytest.mark.django_db
def test_lockout_clears_after_the_window_expires(
    client, make_user, valid_password, cache_clock
):
    """The lockout is a *fixed* 15-minute window, not a permanent block —
    once it elapses, the correct password deletes the account again."""
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
    assert not User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_lockout_window_is_fixed_to_the_first_failure_not_extended_by_later_ones(
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
    assert not User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_fewer_than_five_failures_then_correct_password_still_deletes(
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
    assert not User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_lockout_counter_is_isolated_per_user(client, make_user, valid_password):
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
    assert not User.objects.filter(pk=victim.pk).exists()


@pytest.mark.django_db
def test_correct_password_deletes_user_owned_data_and_media(
    client, make_user, valid_password, png_bytes, settings, tmp_path, django_capture_on_commit_callbacks
):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(password=valid_password)
    entry = PersonalEntry.objects.create(
        user=user,
        kind=PersonalEntry.Kind.PLACE,
        title="탈퇴 테스트 항목",
        image=SimpleUploadedFile("cover.png", png_bytes(), content_type="image/png"),
    )
    storage = entry.image.storage
    file_name = entry.image.name
    assert storage.exists(file_name)

    client.force_login(user)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert not User.objects.filter(pk=user.pk).exists()
    assert not PersonalEntry.objects.filter(pk=entry.pk).exists()
    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_correct_password_deletes_second_degree_cascade_photo_and_media(
    client,
    make_user,
    make_event,
    valid_password,
    png_bytes,
    settings,
    tmp_path,
    django_capture_on_commit_callbacks,
):
    """User -> VisitRecord (1st-degree CASCADE) -> VisitRecordPhoto
    (2nd-degree CASCADE) must still fire archive.signals' post_delete file
    cleanup — the 1st-degree PersonalEntry path is already covered by
    test_correct_password_deletes_user_owned_data_and_media above."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(password=valid_password)
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")
    photo = VisitRecordPhoto.objects.create(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )
    storage = photo.image.storage
    file_name = photo.image.name
    assert storage.exists(file_name)

    client.force_login(user)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert not VisitRecordPhoto.objects.filter(pk=photo.pk).exists()
    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_correct_password_ends_the_session_immediately(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    client.post(DELETE_URL, {"password": valid_password})

    # The browser still holds the old session cookie, but the session was
    # flushed server-side — a protected page must bounce to login.
    response = client.get("/archive/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_deleted_account_can_no_longer_log_in(client, make_user, valid_password):
    user = make_user(email="leaving@example.com", password=valid_password)
    client.force_login(user)
    client.post(DELETE_URL, {"password": valid_password})

    login_response = client.post(
        "/accounts/login/",
        {"login": "leaving@example.com", "password": valid_password},
    )

    assert login_response.status_code == 200  # form re-rendered, not authenticated
    archive_response = client.get("/archive/")
    assert archive_response.status_code == 302
    assert "/accounts/login/" in archive_response["Location"]
