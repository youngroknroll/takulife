"""accounts.services deletion-grace-period internals: cancel/purge race
safety and the purge boundary (no HTTP — see .docs/plans/2026-07-20-deletion-grace-period-plan.md).
"""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from accounts import services
from accounts.models import User
from archive.models import PersonalEntry, VisitRecord, VisitRecordPhoto

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_이미_취소된_탈퇴_예약에_cancel_deletion을_다시_호출하면_아무_효과가_없다(make_user):
    """DEL-12: a concurrent cancel_deletion race (e.g. two logins landing at
    once, or a cancel racing the purge command) must not silently report a
    second success — the rowcount is what the login signal uses to decide
    whether to show a cancellation message, and what execute_pending_deletions
    will use to detect a cancel-vs-purge interleave (DEL-08)."""
    user = make_user()
    services.request_deletion(user)
    stale_user = User.objects.get(pk=user.pk)  # a second caller's fetch
    User.objects.filter(pk=user.pk).update(deletion_requested_at=None)  # already cancelled elsewhere

    rowcount = services.cancel_deletion(stale_user)

    assert rowcount == 0


@pytest.mark.django_db
def test_삭제_예약_후_9일23시간이_지난_계정은_purge_대상이_아니다(make_user):
    """DEL-07 boundary: one hour short of the 10-day grace period must not
    be purged yet — pinned ahead of execute_pending_deletions existing, so
    the boundary is fixed before the sweep logic is written."""
    user = make_user()
    services.request_deletion(user)
    User.objects.filter(pk=user.pk).update(
        deletion_requested_at=timezone.now() - timedelta(days=9, hours=23)
    )

    services.execute_pending_deletions()

    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
def test_삭제_예약_후_10일이_지난_계정은_purge_실행_시_삭제된다(make_user):
    """DEL-06 (base): once the grace period has fully elapsed, the account
    is actually removed — the counterpart to the 9d23h boundary test
    above."""
    user = make_user()
    services.request_deletion(user)
    User.objects.filter(pk=user.pk).update(
        deletion_requested_at=timezone.now() - timedelta(days=10, hours=1)
    )

    services.execute_pending_deletions()

    assert not User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_purge_실행으로_계정이_삭제되면_소유한_직접_등록_항목과_이미지_파일도_함께_삭제된다(
    make_user, png_bytes, settings, tmp_path, django_capture_on_commit_callbacks
):
    """Migrated from tests/auth/test_account_deletion.py's
    test_올바른_비밀번호로_계정을_삭제하면_소유한_직접_등록_항목과_이미지_파일도_함께_삭제된다 (Scenario
    DEL-06, Test Authoring Policy — restoring the protected behavior under the
    new trigger): the trigger is no longer the delete_account view's
    immediate hard delete — it is now execute_pending_deletions, once the
    grace period has elapsed — but the CASCADE + archive.signals file-cleanup
    contract this test protects is unchanged (see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md)."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    entry = PersonalEntry.objects.create(
        user=user,
        kind=PersonalEntry.Kind.PLACE,
        title="탈퇴 테스트 항목",
        image=SimpleUploadedFile("cover.png", png_bytes(), content_type="image/png"),
    )
    storage = entry.image.storage
    file_name = entry.image.name
    assert storage.exists(file_name)

    services.request_deletion(user)
    User.objects.filter(pk=user.pk).update(
        deletion_requested_at=timezone.now() - timedelta(days=10, hours=1)
    )
    with django_capture_on_commit_callbacks(execute=True):
        services.execute_pending_deletions()

    assert not User.objects.filter(pk=user.pk).exists()
    assert not PersonalEntry.objects.filter(pk=entry.pk).exists()
    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_purge_실행으로_계정이_삭제되면_방문_기록의_사진도_2차_연쇄로_삭제된다(
    make_user, make_event, png_bytes, settings, tmp_path, django_capture_on_commit_callbacks
):
    """Migrated from tests/auth/test_account_deletion.py's
    test_올바른_비밀번호로_계정을_삭제하면_방문_기록의_사진도_2차_연쇄로_삭제된다 (Scenario DEL-06, Test
    Authoring Policy): User -> VisitRecord (1st-degree CASCADE) ->
    VisitRecordPhoto (2nd-degree CASCADE) must still fire archive.signals'
    post_delete file cleanup when the delete comes from
    execute_pending_deletions rather than the delete_account view's former
    immediate hard delete."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")
    photo = VisitRecordPhoto.objects.create(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )
    storage = photo.image.storage
    file_name = photo.image.name
    assert storage.exists(file_name)

    services.request_deletion(user)
    User.objects.filter(pk=user.pk).update(
        deletion_requested_at=timezone.now() - timedelta(days=10, hours=1)
    )
    with django_capture_on_commit_callbacks(execute=True):
        services.execute_pending_deletions()

    assert not VisitRecordPhoto.objects.filter(pk=photo.pk).exists()
    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_purge_실행_중_한_계정이_실패해도_나머지_계정은_삭제되고_실패_건수가_요약된다(make_user, monkeypatch):
    """DEL-09: one row's delete failure must not stop the sweep — the
    surviving candidate is still purged, and the failure is surfaced through
    execute_pending_deletions' return value (`{"deleted": [...], "failed":
    [(pk, str(exc)), ...]}`, mirroring discover_drafts.py's per-item
    isolation) rather than swallowed silently."""
    failing_user = make_user()
    surviving_user = make_user()
    services.request_deletion(failing_user)
    services.request_deletion(surviving_user)
    cutoff_backdate = timezone.now() - timedelta(days=10, hours=1)
    User.objects.filter(pk__in=[failing_user.pk, surviving_user.pk]).update(
        deletion_requested_at=cutoff_backdate
    )

    original_delete = User.delete

    def flaky_delete(self, *args, **kwargs):
        if self.pk == failing_user.pk:
            raise RuntimeError("boom")
        return original_delete(self, *args, **kwargs)

    monkeypatch.setattr(User, "delete", flaky_delete)

    summary = services.execute_pending_deletions()

    assert not User.objects.filter(pk=surviving_user.pk).exists()
    assert User.objects.filter(pk=failing_user.pk).exists()
    assert summary["deleted"] == [surviving_user.pk]
    assert len(summary["failed"]) == 1
    failed_pk, failed_reason = summary["failed"][0]
    assert failed_pk == failing_user.pk
    assert "boom" in failed_reason


@pytest.mark.contract
@pytest.mark.django_db
def test_purge_처리_도중_취소가_들어오면_해당_계정은_삭제되지_않는다(make_user, monkeypatch):
    """DEL-08: a cancellation that lands in the gap between the initial
    candidate scan and the per-row select_for_update re-check must win —
    the account survives and is not counted as deleted. This reproduces
    that gap by wrapping `User.objects.select_for_update` so the first call
    triggers `cancel_deletion` for this user *before* delegating to the
    real `select_for_update`, simulating another process's cancel landing
    right before the lock is taken.

    Confirmatory, not a genuine Red: execute_pending_deletions' per-row
    re-verification (`filter(..., deletion_requested_at__lte=cutoff)` after
    `select_for_update`, added in C7) already satisfies this without any
    further change — recorded here as the scenario's coverage, not as a
    manufactured failure."""
    user = make_user()
    services.request_deletion(user)
    User.objects.filter(pk=user.pk).update(
        deletion_requested_at=timezone.now() - timedelta(days=10, hours=1)
    )

    real_select_for_update = User.objects.select_for_update

    def cancel_then_select_for_update(*args, **kwargs):
        services.cancel_deletion(user)
        return real_select_for_update(*args, **kwargs)

    monkeypatch.setattr(User.objects, "select_for_update", cancel_then_select_for_update)

    summary = services.execute_pending_deletions()

    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is None
    assert user.pk not in summary["deleted"]


@pytest.mark.contract
@pytest.mark.django_db
def test_purge_명령어는_실패가_있으면_CommandError를_발생시킨다(make_user, monkeypatch):
    """Thin command-level check: purge_deleted_accounts is a shell around
    execute_pending_deletions, so a row failure must surface as a
    CommandError (never swallowed) — reuses the same flaky-delete mocking
    technique as the service-level failure test above."""
    failing_user = make_user()
    services.request_deletion(failing_user)
    User.objects.filter(pk=failing_user.pk).update(
        deletion_requested_at=timezone.now() - timedelta(days=10, hours=1)
    )

    def flaky_delete(self, *args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(User, "delete", flaky_delete)

    with pytest.raises(CommandError):
        call_command("purge_deleted_accounts")
