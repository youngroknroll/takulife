"""accounts.services 삭제 유예기간 내부 로직: 취소/purge 레이스 안전성과
purge 경계(HTTP 없음 — .docs/plans/2026-07-20-deletion-grace-period-plan.md
참고).
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
    """DEL-12: 동시에 일어난 cancel_deletion 레이스(예: 로그인 두 건이
    동시에 들어오거나, 취소가 purge 명령과 경쟁하는 경우)는 두 번째 성공을
    조용히 보고하면 안 된다 — 이 rowcount로 로그인 시그널이 취소 메시지를
    보여줄지 판단하고, execute_pending_deletions도 이걸로 취소-대-purge
    인터리브(DEL-08)를 감지한다."""
    user = make_user()
    services.request_deletion(user)
    # 두 번째 호출자의 조회
    stale_user = User.objects.get(pk=user.pk)
    # 다른 곳에서 이미 취소됨
    User.objects.filter(pk=user.pk).update(deletion_requested_at=None)

    rowcount = services.cancel_deletion(stale_user)

    assert rowcount == 0


@pytest.mark.django_db
def test_삭제_예약_후_9일23시간이_지난_계정은_purge_대상이_아니다(make_user):
    """DEL-07 경계: 10일 유예기간에서 1시간 모자란 계정은 아직 purge되면
    안 된다 — execute_pending_deletions가 생기기 전에 먼저 고정해 두는
    경계라, 소거 로직을 쓰기 전에 경계값부터 확정한다."""
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
    """DEL-06(기본): 유예기간이 완전히 지나면 계정이 실제로 삭제된다 — 위
    9일 23시간 경계 테스트의 짝이다."""
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
    """DEL-06 시나리오: 지금은 delete_account 뷰의 즉시 하드 삭제가 아니라
    유예기간이 지난 뒤 execute_pending_deletions가 방아쇠지만, 이 테스트가
    지키는 CASCADE + archive.signals 파일 정리 계약 자체는 그대로다
    (.docs/plans/2026-07-20-deletion-grace-period-plan.md 참고)."""
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
    """DEL-06 시나리오: User -> VisitRecord(1차 CASCADE) ->
    VisitRecordPhoto(2차 CASCADE)는, 삭제가 delete_account 뷰의 옛 즉시
    하드 삭제가 아니라 execute_pending_deletions에서 와도 여전히
    archive.signals의 post_delete 파일 정리를 발화해야 한다."""
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
    """DEL-09: 한 행의 삭제 실패가 전체 소거를 멈추면 안 된다 — 살아남은
    후보는 그대로 purge되고, 실패는 조용히 삼켜지지 않고
    execute_pending_deletions의 반환값(`{"deleted": [...], "failed":
    [(pk, str(exc)), ...]}`, discover_drafts.py의 항목별 격리와 같은
    방식)으로 드러난다."""
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
    """DEL-08: 최초 후보 스캔과 행 단위 select_for_update 재확인 사이의
    틈에 들어온 취소가 이겨야 한다 — 계정은 살아남고 삭제됐다고 집계되지
    않는다. 이 틈을 재현하려고 `User.objects.select_for_update`를 감싸,
    첫 호출이 실제 `select_for_update`에 위임하기 *전에* 이 사용자에 대해
    `cancel_deletion`을 먼저 발동시켜 다른 프로세스의 취소가 락을 잡기
    직전에 도착한 상황을 흉내낸다.

    확인용이지 실제 Red는 아니다: execute_pending_deletions의 행 단위
    재검증(`select_for_update` 뒤의 `filter(...,
    deletion_requested_at__lte=cutoff)`, C7에서 추가됨)이 추가 수정 없이
    이미 이걸 만족한다 — 억지로 만든 실패가 아니라 이 시나리오의 커버리지로
    기록해 둔다."""
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
    """얇은 명령어 수준 확인: purge_deleted_accounts는
    execute_pending_deletions를 감싼 껍데기라, 행 실패는 삼켜지지 않고
    CommandError로 드러나야 한다 — 위 서비스 수준 실패 테스트와 같은
    불안정 삭제 모킹 기법을 재사용한다."""
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
