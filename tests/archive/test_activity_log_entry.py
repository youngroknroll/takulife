"""ActivityLogEntry 스키마와 불변식.

(.docs/plans/2026-07-19-dual-calendar-test-list.md 단계 1: CAL-1-01~07)

archive.models.ActivityLogEntry는 아직 없어 이 파일 전체가 모델이 추가되기
전까지 수집 단계에서 ImportError로 실패하는 것이 정상이다.
"""
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import Resolver404, resolve
from django.utils import timezone

from archive.models import ActivityLogEntry


@pytest.mark.domain
@pytest.mark.django_db
def test_필수_필드로_활동_이력을_생성하면_입력한_값이_그대로_저장된다(make_user):
    user = make_user(username="cal-required-fields")
    occurred_at = timezone.now()

    entry = ActivityLogEntry.objects.create(
        user=user,
        kind="interest_added",
        occurred_at=occurred_at,
        subject_label="테스트 이벤트",
    )

    assert entry.user_id == user.id
    assert entry.kind == "interest_added"
    assert entry.occurred_at == occurred_at
    assert entry.subject_label == "테스트 이벤트"
    assert entry.change_summary == {}
    assert entry.operation_key is None
    assert entry.event_id is None
    assert entry.visit_record_id is None
    assert entry.collection_item_id is None


@pytest.mark.contract
@pytest.mark.django_db
def test_타인의_활동_이력은_본인_조회_결과에_포함되지_않는다(make_user):
    user_a = make_user(username="cal-owner-a")
    user_b = make_user(username="cal-owner-b")
    entry_a = ActivityLogEntry.objects.create(
        user=user_a, kind="interest_added", occurred_at=timezone.now(), subject_label="A의 이력"
    )
    ActivityLogEntry.objects.create(
        user=user_b, kind="interest_added", occurred_at=timezone.now(), subject_label="B의 이력"
    )

    result_ids = list(ActivityLogEntry.objects.filter(user=user_a).values_list("id", flat=True))

    assert result_ids == [entry_a.id]


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "reuse_same_key",
    [True, False],
    ids=["동일_키_재사용_거부", "키_없음_다건_허용"],
)
def test_operation_key_유니크_제약은_동일_키만_거부하고_NULL_키는_다건_허용한다(
    make_user, reuse_same_key
):
    user = make_user(username=f"cal-operation-key-{reuse_same_key}")

    if reuse_same_key:
        key = uuid.uuid4()
        ActivityLogEntry.objects.create(
            user=user,
            kind="interest_added",
            occurred_at=timezone.now(),
            subject_label="첫 이력",
            operation_key=key,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ActivityLogEntry.objects.create(
                    user=user,
                    kind="interest_added",
                    occurred_at=timezone.now(),
                    subject_label="재생 이력",
                    operation_key=key,
                )
    else:
        ActivityLogEntry.objects.create(
            user=user,
            kind="interest_added",
            occurred_at=timezone.now(),
            subject_label="첫 이력",
            operation_key=None,
        )
        ActivityLogEntry.objects.create(
            user=user,
            kind="interest_added",
            occurred_at=timezone.now(),
            subject_label="둘째 이력",
            operation_key=None,
        )

        assert ActivityLogEntry.objects.filter(user=user).count() == 2


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "subject_kind",
    ["이벤트", "방문기록", "컬렉션아이템"],
    ids=["이벤트", "방문기록", "컬렉션아이템"],
)
def test_연결_대상이_삭제되면_FK는_null이_되고_최소_스냅샷은_남는다(
    make_user, make_event, make_visit, make_collection_item, subject_kind
):
    user = make_user(username=f"cal-fk-null-{subject_kind}")

    if subject_kind == "이벤트":
        related = make_event(title="삭제될 행사")
        entry = ActivityLogEntry.objects.create(
            user=user,
            kind="interest_added",
            occurred_at=timezone.now(),
            subject_label="삭제될 행사",
            event=related,
        )
        fk_field = "event_id"
    elif subject_kind == "방문기록":
        event = make_event(title="방문 대상 행사")
        related = make_visit(user, event=event, visited_on="2026-01-01")
        entry = ActivityLogEntry.objects.create(
            user=user,
            kind="visit_record_created",
            occurred_at=timezone.now(),
            subject_label="삭제될 방문 기록",
            visit_record=related,
        )
        fk_field = "visit_record_id"
    else:
        related = make_collection_item(user, name="삭제될 굿즈")
        entry = ActivityLogEntry.objects.create(
            user=user,
            kind="collection_item_created",
            occurred_at=timezone.now(),
            subject_label="삭제될 굿즈",
            collection_item=related,
        )
        fk_field = "collection_item_id"

    related.delete()
    entry.refresh_from_db()

    assert getattr(entry, fk_field) is None
    assert entry.subject_label


@pytest.mark.domain
@pytest.mark.django_db
def test_계정을_삭제하면_보유한_활동_이력도_함께_삭제된다(make_user):
    user = make_user(username="cal-cascade-user")
    entry = ActivityLogEntry.objects.create(
        user=user,
        kind="interest_added",
        occurred_at=timezone.now(),
        subject_label="계정과 함께 사라질 이력",
    )
    entry_id = entry.id

    user.delete()

    assert not ActivityLogEntry.objects.filter(id=entry_id).exists()


@pytest.mark.domain
@pytest.mark.django_db
def test_정의되지_않은_kind_값으로_저장을_시도하면_거부된다(make_user):
    user = make_user(username="cal-invalid-kind")
    entry = ActivityLogEntry(
        user=user,
        kind="no_such_kind",
        occurred_at=timezone.now(),
        subject_label="잘못된 종류",
    )

    with pytest.raises(ValidationError):
        entry.full_clean()


@pytest.mark.contract
@pytest.mark.parametrize(
    "path",
    ["/api/activity-log-entries/", "/api/activity-log-entries/1/"],
    ids=["목록_생성", "상세"],
)
def test_활성_urlconf에는_활동_이력을_다루는_공개_라우트가_없다(path):
    with pytest.raises(Resolver404):
        resolve(path)
