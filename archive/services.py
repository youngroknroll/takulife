from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.analytics import record_event
from core.models import AnalyticsEvent

from .models import (
    ActivityLogEntry,
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)
from .signals import _delete_file_best_effort


MAX_PHOTOS_PER_RECORD = 5

# 이 필드들이 실제로 바뀔 때만 collection_item_organized로 기록한다 —
# memo/image 등은 단순 수정일 뿐 "정리"가 아니다.
_COLLECTION_ITEM_ORGANIZE_FIELDS = ("quantity", "is_wanted", "tradeable_quantity", "acquired_on")

# UserEventStatus.Status -> 그 상태로 생성될 때 남기는 AnalyticsEvent.
# MISSED는 없다: PLANNED/VISITED만 0단계 컬렉션 퍼널 이벤트이고,
# 처음부터 MISSED로 만들어진 상태 행은 대응하는 "퍼널 단계"가 없다.
_STATUS_ANALYTICS_EVENT_NAME = {
    UserEventStatus.Status.PLANNED: AnalyticsEvent.EventName.EVENT_PLANNED,
    UserEventStatus.Status.VISITED: AnalyticsEvent.EventName.EVENT_MARKED_VISITED,
}


def _subject_target(*, event=None, personal_entry=None):
    """주어진 대상(event 또는 personal_entry)에 맞는 (target_type, target_id)를 반환한다."""
    if event is not None:
        return "event", event.id
    return "personal_entry", personal_entry.id


def _subject_label(*, event=None, personal_entry=None):
    """주어진 대상의 표시용 제목을 반환한다. 대상 행이 나중에 삭제돼도
    이 문자열은 ActivityLogEntry에 남아 이력을 보존한다."""
    if event is not None:
        return event.title
    return personal_entry.title


def _record_activity(
    *,
    user,
    kind,
    subject_label,
    occurred_at=None,
    event=None,
    visit_record=None,
    collection_item=None,
    change_summary=None,
    operation_key=None,
):
    """ActivityLogEntry 한 행을 기록한다. 모듈 비공개 함수이며, 항상 해당
    활동을 처리하는 서비스 함수와 같은 트랜잭션 안에서만 호출한다.
    시그널에서 호출하거나 별도 공개 진입점으로 노출하지 않는다."""
    ActivityLogEntry.objects.create(
        user=user,
        kind=kind,
        occurred_at=occurred_at or timezone.now(),
        event=event,
        visit_record=visit_record,
        collection_item=collection_item,
        subject_label=subject_label,
        change_summary=change_summary or {},
        operation_key=operation_key,
    )


def _json_safe_change_value(value):
    """허용된 change_summary 값 하나를 JSON에 안전한 값으로 바꾼다.
    `date`는 ISO 문자열로 바꾸고, `int`/`bool`/`None`(다른
    _COLLECTION_ITEM_ORGANIZE_FIELDS 값 타입)은 이미 JSON으로 그대로
    오갈 수 있어 그대로 둔다."""
    if isinstance(value, date):
        return value.isoformat()
    return value


def create_personal_entry(*, user, kind, title, client_token=None, **fields):
    """소유자 본인에게만 비공개인 비공식 기록을 만든다.

    PersonalEntry는 비공식 장소로만 제한된다 — 굿즈는 별도의
    CollectionItem 도메인으로 옮겨졌으므로 여기서는 만들 수 없다.

    `client_token`은 클라이언트가 발급하는 멱등 키다. 같은
    (user, client_token)으로 재전송된 요청은 UniqueConstraint에 걸려
    새 항목이 아니라 "이미 생성됨"으로 처리한다 — 기존 행을 그대로
    조회해 반환할 뿐, 재전송된 값으로 덮어쓰지 않는다. 이 재조회는
    atomic 블록 *밖*에서 해야 한다. 블록 안에서 잡으면 이미 중단된
    트랜잭션에 쿼리를 날리게 되는데, PostgreSQL은 세이브포인트가
    롤백되기 전까지 그 이후의 문장을 금지한다.
    """
    if kind != PersonalEntry.Kind.PLACE:
        raise ValidationError({"kind": "place 외의 kind로는 PersonalEntry를 생성할 수 없습니다."})
    try:
        with transaction.atomic():
            return PersonalEntry.objects.create(
                user=user, kind=kind, title=title, client_token=client_token, **fields
            )
    except IntegrityError:
        if client_token is None:
            raise
        return PersonalEntry.objects.get(user=user, client_token=client_token)


class DuplicateUserEventStatusError(Exception):
    pass


class DuplicateEventInterestError(Exception):
    pass


def create_event_interest(*, user, event=None, personal_entry=None):
    with transaction.atomic():
        try:
            interest = EventInterest.objects.create(
                user=user, event=event, personal_entry=personal_entry
            )
        except IntegrityError as exc:
            raise DuplicateEventInterestError from exc
        _record_activity(
            user=user,
            kind=ActivityLogEntry.Kind.INTEREST_ADDED,
            event=event,
            subject_label=_subject_label(event=event, personal_entry=personal_entry),
        )
    target_type, target_id = _subject_target(event=event, personal_entry=personal_entry)
    record_event(
        event_name=AnalyticsEvent.EventName.EVENT_INTERESTED,
        user=user,
        target_type=target_type,
        target_id=target_id,
    )
    return interest


def remove_event_interest(*, interest):
    """EventInterest를 삭제하고 interest_removed 활동 기록을 남긴다.
    user/event/subject_label을 삭제 전에 미리 담아둬야, 행이 지워진
    뒤에도 이 기록이 남는다."""
    user = interest.user
    event = interest.event
    subject_label = _subject_label(event=interest.event, personal_entry=interest.personal_entry)
    with transaction.atomic():
        interest.delete()
        _record_activity(
            user=user,
            kind=ActivityLogEntry.Kind.INTEREST_REMOVED,
            event=event,
            subject_label=subject_label,
        )


def create_user_event_status(*, user, event=None, personal_entry=None, status):
    with transaction.atomic():
        # 주어진 대상 기준으로 중복 여부를 미리 확인한다(모델의 조건부
        # unique 제약이 DB 단에서 한 번 더 보장해 준다).
        existing = UserEventStatus.objects.filter(user=user)
        if event is not None:
            existing = existing.filter(event=event)
        else:
            existing = existing.filter(personal_entry=personal_entry)
        if existing.exists():
            raise DuplicateUserEventStatusError
        # mark_missed/revert_to_planned가 PATCH에서 지키는 것과 같은
        # 불변식이다: 이미 VisitRecord가 있는 대상에는 새 planned/missed
        # 행을 만들 수 없다. 아니면 DELETE 후 POST로 예전에 바로잡았던
        # 어긋남이 재현된다. visited는 예외인데, 기록과 모순되지 않고
        # 오히려 일치하기 때문이다.
        if status in (
            UserEventStatus.Status.PLANNED,
            UserEventStatus.Status.MISSED,
        ) and _has_visit_record(user=user, event=event, personal_entry=personal_entry):
            raise VisitRecordExistsError
        try:
            created = UserEventStatus.objects.create(
                user=user, event=event, personal_entry=personal_entry, status=status
            )
        except IntegrityError as exc:
            raise DuplicateUserEventStatusError from exc
        _record_activity(
            user=user,
            kind=ActivityLogEntry.Kind.STATUS_CHANGED,
            event=event,
            subject_label=_subject_label(event=event, personal_entry=personal_entry),
            change_summary={"to": status},
        )
    event_name = _STATUS_ANALYTICS_EVENT_NAME.get(status)
    if event_name is not None:
        target_type, target_id = _subject_target(event=event, personal_entry=personal_entry)
        record_event(event_name=event_name, user=user, target_type=target_type, target_id=target_id)
    return created


def mark_visited(*, user_event_status):
    """상태 행을 방문(예: '실제로 다녀왔다')으로 바꾼다."""
    previous_status = user_event_status.status
    user_event_status.status = UserEventStatus.Status.VISITED
    user_event_status.save(update_fields=["status", "updated_at"])
    if previous_status != UserEventStatus.Status.VISITED:
        _record_activity(
            user=user_event_status.user,
            kind=ActivityLogEntry.Kind.STATUS_CHANGED,
            event=user_event_status.event,
            subject_label=_subject_label(
                event=user_event_status.event, personal_entry=user_event_status.personal_entry
            ),
            change_summary={"from": previous_status, "to": UserEventStatus.Status.VISITED},
        )
    target_type, target_id = _subject_target(
        event=user_event_status.event, personal_entry=user_event_status.personal_entry
    )
    record_event(
        event_name=AnalyticsEvent.EventName.EVENT_MARKED_VISITED,
        user=user_event_status.user,
        target_type=target_type,
        target_id=target_id,
    )
    return user_event_status


class VisitRecordExistsError(Exception):
    """이미 VisitRecord가 있는 대상을 상태만 PATCH하거나 새로 생성해서
    예정/놓침으로 만들려고 할 때 발생시킨다. VisitRecord가 있으면 그
    이후로는 상태 행이 아니라 VisitRecord가 진실의 원천이다."""


def _has_visit_record(*, user, event, personal_entry):
    queryset = VisitRecord.objects.filter(user=user)
    if event is not None:
        queryset = queryset.filter(event=event)
    else:
        queryset = queryset.filter(personal_entry=personal_entry)
    return queryset.exists()


def mark_missed(*, user_event_status):
    """상태 행을 명시적으로 놓침으로 바꾼다. 행사 날짜 전이든 후든 동작한다."""
    if _has_visit_record(
        user=user_event_status.user,
        event=user_event_status.event,
        personal_entry=user_event_status.personal_entry,
    ):
        raise VisitRecordExistsError
    previous_status = user_event_status.status
    user_event_status.status = UserEventStatus.Status.MISSED
    user_event_status.save(update_fields=["status", "updated_at"])
    if previous_status != UserEventStatus.Status.MISSED:
        _record_activity(
            user=user_event_status.user,
            kind=ActivityLogEntry.Kind.STATUS_CHANGED,
            event=user_event_status.event,
            subject_label=_subject_label(
                event=user_event_status.event, personal_entry=user_event_status.personal_entry
            ),
            change_summary={"from": previous_status, "to": UserEventStatus.Status.MISSED},
        )
    return user_event_status


def revert_to_planned(*, user_event_status):
    """행을 다시 예정으로 고정하고 자동 놓침 처리에서 제외한다.

    ``missed_overridden``을 설정해야 이 선택이 유지된다. 아니면 조회 시
    계산 로직이 종료된 예정 행을 다시 놓침으로 보여준다.
    """
    if _has_visit_record(
        user=user_event_status.user,
        event=user_event_status.event,
        personal_entry=user_event_status.personal_entry,
    ):
        raise VisitRecordExistsError
    previous_status = user_event_status.status
    user_event_status.status = UserEventStatus.Status.PLANNED
    user_event_status.missed_overridden = True
    user_event_status.save(update_fields=["status", "missed_overridden", "updated_at"])
    if previous_status != UserEventStatus.Status.PLANNED:
        _record_activity(
            user=user_event_status.user,
            kind=ActivityLogEntry.Kind.STATUS_CHANGED,
            event=user_event_status.event,
            subject_label=_subject_label(
                event=user_event_status.event, personal_entry=user_event_status.personal_entry
            ),
            change_summary={"from": previous_status, "to": UserEventStatus.Status.PLANNED},
        )
    return user_event_status


def remove_user_event_status(*, user_event_status):
    """UserEventStatus를 삭제하고 status_removed 활동 기록을 남긴다.
    user/event/subject_label을 삭제 전에 미리 담아둬야, 행이 지워진
    뒤에도 이 기록이 남는다."""
    user = user_event_status.user
    event = user_event_status.event
    subject_label = _subject_label(
        event=user_event_status.event, personal_entry=user_event_status.personal_entry
    )
    with transaction.atomic():
        user_event_status.delete()
        _record_activity(
            user=user,
            kind=ActivityLogEntry.Kind.STATUS_REMOVED,
            event=event,
            subject_label=subject_label,
        )


def create_collection_item(*, user, name, visit_record=None, event=None, client_token=None, **fields):
    """사용자 소유의 굿즈 컬렉션 항목을 생성한다.

    `visit_record`가 주어지면 `event`는 항상 `visit_record.event`로
    맞춘다 — visit_record 자신이 가리키는 대상이 명시적으로 넘어온
    `event`보다 우선이라, 두 링크가 서로 어긋날 수 없다. `visit_record`는
    반드시 `user` 소유여야 하며, 다른 사용자의 visit_record를 붙이려는
    시도는 교차 사용자 데이터 유출로 이어지기 전에 여기서 막는다.

    수량 불변식(quantity >= 0, 0 <= tradeable_quantity <= quantity)은
    삽입 *전에* 여기서 한 번 더 ValidationError로 검사한다 — 진실의
    원천은 DB CheckConstraint이고, 이건 "모델 제약 + 애플리케이션
    서비스"라는 이중 방어의 서비스 쪽 절반일 뿐 그것을 대체하지 않는다.

    `client_token`은 클라이언트가 발급하는 멱등 키다. 같은
    (user, client_token)으로 재전송된 요청은 UniqueConstraint에 걸려
    새 항목이 아니라 "이미 생성됨"으로 처리한다 — 기존 행을 그대로
    조회해 반환할 뿐 재전송된 값으로 덮어쓰지 않으며, 이 처리는 아래
    분석 이벤트 호출보다 *먼저* 일어나므로 재전송이 행뿐 아니라 분석
    이벤트에 대해서도 정확히 한 번만 일어난다. 이 재조회는 atomic
    블록 *밖*에서 해야 한다. 블록 안에서 잡으면 이미 중단된 트랜잭션에
    쿼리를 날리게 되는데, PostgreSQL은 세이브포인트가 롤백되기 전까지
    그 이후의 문장을 금지한다.
    """
    quantity = fields.get("quantity", CollectionItem._meta.get_field("quantity").default)
    tradeable_quantity = fields.get(
        "tradeable_quantity", CollectionItem._meta.get_field("tradeable_quantity").default
    )
    errors = {}
    if quantity < 0:
        errors["quantity"] = "quantity는 0 이상이어야 합니다."
    if tradeable_quantity < 0:
        errors["tradeable_quantity"] = "tradeable_quantity는 0 이상이어야 합니다."
    elif tradeable_quantity > quantity:
        errors["tradeable_quantity"] = "tradeable_quantity는 quantity 이하여야 합니다."
    if errors:
        raise ValidationError(errors)

    if visit_record is not None:
        if visit_record.user_id != user.id:
            raise ValidationError(
                {"visit_record": "visit_record는 요청한 사용자의 소유여야 합니다."}
            )
        event = visit_record.event

    try:
        with transaction.atomic():
            item = CollectionItem.objects.create(
                user=user,
                name=name,
                visit_record=visit_record,
                event=event,
                client_token=client_token,
                **fields,
            )
            _record_activity(
                user=user,
                kind=ActivityLogEntry.Kind.COLLECTION_ITEM_CREATED,
                collection_item=item,
                subject_label=item.name,
                operation_key=client_token,
            )
    except IntegrityError:
        if client_token is None:
            raise
        return CollectionItem.objects.get(user=user, client_token=client_token)
    record_event(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_CREATED,
        user=user,
        target_type="collection_item",
        target_id=item.id,
    )
    if visit_record is not None:
        record_event(
            event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT,
            user=user,
            target_type="collection_item",
            target_id=item.id,
        )
    if fields.get("is_wanted"):
        record_event(
            event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED,
            user=user,
            target_type="collection_item",
            target_id=item.id,
        )
    if fields.get("tradeable_quantity", 0) > 0:
        record_event(
            event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_TRADEABLE,
            user=user,
            target_type="collection_item",
            target_id=item.id,
        )
    return item


def _event_alone_targets_existing_visit_record(item, fields) -> bool:
    """이번 PATCH가 visit_record는 건드리지 않았지만 event는 있고, 항목엔 이미
    visit_record가 연결돼 있으면 True."""
    return item.visit_record_id is not None and "event" in fields


def update_collection_item(*, item, **fields):
    """기존 CollectionItem의 수정 가능한 필드를 갱신한다.

    create_collection_item과 같은 불변식 검사를 *병합된*(기존 값 +
    새 입력) 값에 대해 적용한다 — 그래야 부분 PATCH가 병합을 무효로
    만드는 필드를 생략하는 방식으로 검사를 우회할 수 없다. `visit_record`
    가 주어지면(null이 아니면) create_collection_item과 똑같이 `event`를
    `visit_record.event`로 맞추므로 두 링크가 어긋날 수 없고,
    `visit_record`는 반드시 항목 소유자의 것이어야 한다.

    FK 짝 검사는 *병합된* 값(fields.get(..., item.X))을 읽는다. 아래
    수량 검사와 같은 방식이다 — `event`만 건드리거나 둘 다 생략한
    PATCH가 생략만으로 짝을 조용히 어긋나게 둘 수 없다(과거 버전은
    모델 clean()만 검사했는데, 병합된 event가 None이면 그게 발동하지
    않아 visit_record가 연결된 행에 `PATCH {"event": null}`이 그대로
    통과했다). `PATCH {"visit_record": null}`로 명시적으로 연결을 끊는
    것은 영향받지 않는다 — visit_record 자체가 비면 이 짝 검사에서
    빠진다.

    다른 대입 경로도 모델의 clean() FK 짝 검사가 잡을 수 있도록
    full_clean()도 실행한다.

    transaction.atomic() + select_for_update() 안에서 실행하고(
    create_visit_record_photo의 개수 검사 경합 방지와 같은 방식), 그 락
    아래에서 `item`을 다시 조회한 뒤에야 병합 값을 계산한다 — 그렇지
    않으면 동시에 들어온 두 PATCH가 각자 오래된 스냅샷을 기준으로
    병합 검사를 통과하고, 한쪽이 상대가 이미 커밋한 상태와 충돌하는
    값을 커밋해 깔끔한 400이 아니라 처리되지 않은 IntegrityError로
    새어 나갈 수 있다.
    """
    with transaction.atomic():
        item = CollectionItem.objects.select_for_update().get(pk=item.pk)
        previous_visit_record_id = item.visit_record_id
        previous_is_wanted = item.is_wanted
        previous_tradeable_quantity = item.tradeable_quantity
        previous_organize_values = {
            field_name: getattr(item, field_name)
            for field_name in _COLLECTION_ITEM_ORGANIZE_FIELDS
        }

        quantity = fields.get("quantity", item.quantity)
        tradeable_quantity = fields.get("tradeable_quantity", item.tradeable_quantity)
        errors = {}
        if quantity < 0:
            errors["quantity"] = "quantity는 0 이상이어야 합니다."
        if tradeable_quantity < 0:
            errors["tradeable_quantity"] = "tradeable_quantity는 0 이상이어야 합니다."
        elif tradeable_quantity > quantity:
            errors["tradeable_quantity"] = "tradeable_quantity는 quantity 이하여야 합니다."
        if errors:
            raise ValidationError(errors)

        if "visit_record" in fields:
            visit_record = fields["visit_record"]
            if visit_record is not None:
                if visit_record.user_id != item.user_id:
                    raise ValidationError(
                        {"visit_record": "visit_record는 아이템 소유자의 소유여야 합니다."}
                    )
                fields["event"] = visit_record.event
            # else: visit_record를 명시적으로 비운 경우 — event는 페이로드
            # 값이든 기존 값이든 자유롭게 둔다. visit_record가 사라지면
            # FK 짝 불변식도 더 이상 적용되지 않는다.
        elif _event_alone_targets_existing_visit_record(item, fields):
            # 병합된 event가 여전히 visit_record.event와 일치해야 한다.
            if fields["event"] != item.visit_record.event:
                raise ValidationError(
                    {
                        "event": (
                            "visit_record가 설정된 경우 event는 "
                            "visit_record.event와 일치해야 합니다."
                        )
                    }
                )

        # 이 수정이 교체하려는 파일을 인스턴스를 바꾸기 *전에* 미리
        # 붙잡아 둔다 — Django의 FieldFile 재할당은 기존 저장 파일을
        # 스스로 지우지 않고, post_delete는 행 삭제 때만 발동하며 제자리
        # 수정에는 발동하지 않는다. 지금 참조를 잡아두는 건 안전하다.
        # 아래에서 item.image를 재할당해도 이미 붙잡아 둔 FieldFile
        # 객체 자체는 바뀌지 않는다.
        old_image = item.image if "image" in fields else None
        old_image_name = old_image.name if old_image else None

        for field_name, value in fields.items():
            setattr(item, field_name, value)

        item.full_clean()
        update_fields = set(fields.keys())
        update_fields.add("updated_at")
        item.save(update_fields=update_fields)

        organize_changes = {
            field_name: _json_safe_change_value(getattr(item, field_name))
            for field_name in _COLLECTION_ITEM_ORGANIZE_FIELDS
            if field_name in fields
            and getattr(item, field_name) != previous_organize_values[field_name]
        }
        if organize_changes:
            _record_activity(
                user=item.user,
                kind=ActivityLogEntry.Kind.COLLECTION_ITEM_ORGANIZED,
                collection_item=item,
                subject_label=item.name,
                change_summary=organize_changes,
            )

    new_image_name = item.image.name if item.image else None
    if old_image_name and old_image_name != new_image_name:
        _delete_file_best_effort(old_image)

    record_event(
        event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_UPDATED,
        user=item.user,
        target_type="collection_item",
        target_id=item.id,
    )
    if item.visit_record_id is not None and previous_visit_record_id is None:
        record_event(
            event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_LINKED_TO_VISIT,
            user=item.user,
            target_type="collection_item",
            target_id=item.id,
        )
    if item.is_wanted and not previous_is_wanted:
        record_event(
            event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_WANTED,
            user=item.user,
            target_type="collection_item",
            target_id=item.id,
        )
    if item.is_tradeable and previous_tradeable_quantity == 0:
        record_event(
            event_name=AnalyticsEvent.EventName.COLLECTION_ITEM_MARKED_TRADEABLE,
            user=item.user,
            target_type="collection_item",
            target_id=item.id,
        )
    return item


def create_visit_record(
    *, user, event=None, personal_entry=None, visited_on, short_review="", client_token=None
):
    """방문 기록을 생성한다.

    `client_token`은 클라이언트가 발급하는 멱등 키다. 같은
    (user, client_token)으로 재전송된 요청은 UniqueConstraint에 걸려
    새 기록이 아니라 "이미 생성됨"으로 처리한다 — 기존 행을 그대로
    조회해 반환할 뿐 재전송된 값으로 덮어쓰지 않으며, 이 처리는 아래
    분석 이벤트 호출보다 *먼저* 일어나므로 재전송이 행뿐 아니라 분석
    이벤트에 대해서도 정확히 한 번만 일어난다. 이 재조회는 atomic
    블록 *밖*에서 해야 한다. 블록 안에서 잡으면 이미 중단된 트랜잭션에
    쿼리를 날리게 되는데, PostgreSQL은 세이브포인트가 롤백되기 전까지
    그 이후의 문장을 금지한다. atomic 블록을 안쪽으로 좁혀 둔 이유는,
    이 함수가 `complete_visit_with_record`의 바깥 `transaction.atomic()`
    안에서 실행될 때 여기서 잡힌 IntegrityError가 이 세이브포인트만
    되돌리고 바깥의 상태 동기화 트랜잭션까지 되돌리지 않게 하기
    위해서다.
    """
    try:
        with transaction.atomic():
            record = VisitRecord.objects.create(
                user=user,
                event=event,
                personal_entry=personal_entry,
                visited_on=visited_on,
                short_review=short_review,
                client_token=client_token,
            )
            _record_activity(
                user=user,
                kind=ActivityLogEntry.Kind.VISIT_RECORD_CREATED,
                event=event,
                visit_record=record,
                subject_label=_subject_label(event=event, personal_entry=personal_entry),
                operation_key=client_token,
            )
    except IntegrityError:
        if client_token is None:
            raise
        return VisitRecord.objects.get(user=user, client_token=client_token)
    target_type, target_id = _subject_target(event=event, personal_entry=personal_entry)
    # short_review는 사용자가 자유롭게 입력한 텍스트라 개인정보로 취급해
    # 의도적으로 context에서 뺀다(record_event의 금지된 context 키 중 하나).
    record_event(
        event_name=AnalyticsEvent.EventName.VISIT_RECORD_CREATED,
        user=user,
        target_type=target_type,
        target_id=target_id,
    )
    return record


def complete_visit_with_record(
    *, user, event=None, personal_entry=None, visited_on, short_review="", client_token=None
):
    """방문 완료와 경험 기록을 하나의 트랜잭션으로 함께 처리한다.
    상태 행을 자동으로 맞춰주므로, 방문 기록은 있는데 그 상태 행이
    "방문"과 어긋나는 상태로 존재할 수 없다. `client_token`은
    `create_visit_record`의 멱등 재전송 검사로 그대로 전달된다. 이
    호출을 재전송해도 상태 쪽은 자연히 아무 일도 일어나지 않는데,
    재전송이 도착할 즈음엔 첫 호출로 이미 status_row가 VISITED가
    되어 있어 생성/mark_visited 어느 분기도 다시 실행되지 않기
    때문이다.
    """
    with transaction.atomic():
        existing = UserEventStatus.objects.filter(user=user)
        if event is not None:
            existing = existing.filter(event=event)
        else:
            existing = existing.filter(personal_entry=personal_entry)
        status_row = existing.first()

        if status_row is None:
            create_user_event_status(
                user=user,
                event=event,
                personal_entry=personal_entry,
                status=UserEventStatus.Status.VISITED,
            )
        elif status_row.status != UserEventStatus.Status.VISITED:
            mark_visited(user_event_status=status_row)

        return create_visit_record(
            user=user,
            event=event,
            personal_entry=personal_entry,
            visited_on=visited_on,
            short_review=short_review,
            client_token=client_token,
        )


def update_visit_record(*, record, visited_on, short_review):
    """기존 기록의 수정 가능한 필드를 갱신한다. 대상은 바뀌지 않고 고정된다."""
    record.visited_on = visited_on
    record.short_review = short_review
    record.save(update_fields=["visited_on", "short_review"])
    return record


class PhotoLimitExceededError(Exception):
    pass


def create_visit_record_photo(*, visit_record, image, client_token=None):
    """VisitRecord에 사진을 추가한다(사진은 사용자 소유 최상위 대상이
    아니라 VisitRecord의 하위 행이다).

    `client_token`은 클라이언트가 발급하는 멱등 키이며, (user,
    client_token)이 아니라 (visit_record, client_token) 단위로
    스코프한다(이유는 VisitRecordPhoto의 UniqueConstraint 참고).

    토큰 재전송 검사는 아래 개수 검사와 같은 락 안에서 *가장 먼저*
    실행한다 — 락을 잡기 전도 아니고 상한 검사 뒤도 아니다. 이 키가
    존재하는 실제 이유는 MAX_PHOTOS_PER_RECORD를 채운 바로 그 업로드가
    재전송되는 경우(응답 유실 후 클라이언트 재시도)인데, 상한 검사를
    먼저 하면 이미 존재하는 행이 반환되지 않고 "하나 초과"로 거부돼
    버린다. 락을 잡기 전에 값싸게 먼저 조회하지 않고 락을 잡은 뒤에
    조회하는 것은 추가 비용이 없다 — 어차피 뒤이은 개수 검사 때문에
    모든 호출이 이 락을 잡기 때문이다. 그리고 같은 (visit_record,
    client_token)에 대한 동시 요청은 이 락에서 대기했다가 이미 커밋된
    행을 이 조회로 보게 되므로, 상한 검사와 경합하지 않는다. 아래
    IntegrityError 처리는 이 함수의 락 범위 밖(예: 이 락을 우회하는
    raw insert)을 위한 2차 방어로 남겨두었고, 그 재조회도 atomic
    블록 *밖*에서 해야 한다. 블록 안에서 잡으면 이미 중단된 트랜잭션에
    쿼리를 날리게 되는데, PostgreSQL은 세이브포인트가 롤백되기 전까지
    그 이후의 문장을 금지한다(create_personal_entry와 같은 방식).
    """
    try:
        with transaction.atomic():
            locked_record = VisitRecord.objects.select_for_update().get(pk=visit_record.pk)
            if client_token is not None:
                existing = locked_record.photos.filter(client_token=client_token).first()
                if existing is not None:
                    return existing
            if locked_record.photos.count() >= MAX_PHOTOS_PER_RECORD:
                raise PhotoLimitExceededError
            photo = VisitRecordPhoto.objects.create(
                visit_record=locked_record, image=image, client_token=client_token
            )
    except IntegrityError:
        if client_token is None:
            raise
        return VisitRecordPhoto.objects.get(visit_record=visit_record, client_token=client_token)
    record_event(
        event_name=AnalyticsEvent.EventName.VISIT_PHOTO_ADDED,
        user=locked_record.user,
        target_type="visit_record_photo",
        target_id=photo.id,
    )
    return photo
