from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from events.models import Event

from .querysets import UserEventStatusQuerySet


class EventInterest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_event_interests",
    )
    # 대상은 공식 event와 비공식 personal_entry 중 정확히 하나여야 한다.
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="archive_user_interests",
        null=True,
        blank=True,
    )
    personal_entry = models.ForeignKey(
        "PersonalEntry",
        on_delete=models.CASCADE,
        related_name="archive_user_interests",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="eventinterest_exactly_one_subject",
                condition=(
                    models.Q(event__isnull=False, personal_entry__isnull=True)
                    | models.Q(event__isnull=True, personal_entry__isnull=False)
                ),
            ),
            models.UniqueConstraint(
                fields=["user", "event"],
                condition=models.Q(event__isnull=False),
                name="unique_archive_user_event_interest",
            ),
            models.UniqueConstraint(
                fields=["user", "personal_entry"],
                condition=models.Q(personal_entry__isnull=False),
                name="unique_archive_user_personal_interest",
            ),
        ]


class UserEventStatus(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        VISITED = "visited", "Visited"
        MISSED = "missed", "Missed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_event_statuses",
    )
    # 대상은 공식 event와 비공식 personal_entry 중 정확히 하나여야 한다.
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="archive_user_statuses",
        null=True,
        blank=True,
    )
    personal_entry = models.ForeignKey(
        "PersonalEntry",
        on_delete=models.CASCADE,
        related_name="archive_user_statuses",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    # 사용자가 자동 '놓침' 처리를 거부하고 '예정'으로 되돌린 경우 True.
    # 상태가 이미 방문/놓침으로 확정된 행에는 영향을 주지 않는다.
    missed_overridden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserEventStatusQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="usereventstatus_exactly_one_subject",
                condition=(
                    models.Q(event__isnull=False, personal_entry__isnull=True)
                    | models.Q(event__isnull=True, personal_entry__isnull=False)
                ),
            ),
            models.UniqueConstraint(
                fields=["user", "event"],
                condition=models.Q(event__isnull=False),
                name="unique_archive_user_event_status",
            ),
            models.UniqueConstraint(
                fields=["user", "personal_entry"],
                condition=models.Q(personal_entry__isnull=False),
                name="unique_archive_user_personal_status",
            ),
        ]


class PersonalEntry(models.Model):
    """사용자 소유의 비공식 기록.

    관리자 검수를 거쳐 공개되는 Event와 달리, 사용자가 직접 찾거나 소유한
    비공식 굿즈샵·구매품 등이다. 항상 소유자 본인에게만 비공개이며 공개
    카탈로그에는 절대 노출되지 않는다.
    """

    class Kind(models.TextChoices):
        PLACE = "place", "Place"

    class PromotionStatus(models.TextChoices):
        # ""=공식 검수에 제출된 적 없음, "submitted"=검수용 초안이 생성됨.
        # archive는 drafts에 의존하면 안 되므로 drafts를 향한 FK가 아니라
        # 중립적인 core.promotion 조정자가 이 값을 설정한다.
        NONE = "", "None"
        SUBMITTED = "submitted", "Submitted"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_personal_entries",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    work_title = models.CharField(max_length=255, blank=True)
    location_name = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=100, blank=True)
    # 사용자가 남기는 참고 링크(트윗/블로그/샵)로, 유일값도 공식 출처도 아니다.
    url = models.URLField(blank=True)
    memo = models.TextField(blank=True)
    image = models.ImageField(upload_to="personal-entries/", blank=True, null=True)
    promotion_status = models.CharField(
        max_length=20,
        choices=PromotionStatus.choices,
        default=PromotionStatus.NONE,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # bfcache 재생 등으로 같은 요청이 중복 전송돼도 한 번만 처리되도록
    # 클라이언트가 발급하는 멱등 키. 사용자가 직접 수정할 수 없고, 이
    # 필드가 생기기 전에 만들어진 행은 비어 있다(null).
    client_token = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "client_token"],
                condition=models.Q(client_token__isnull=False),
                name="unique_archive_personal_entry_user_client_token",
            ),
        ]

    def __str__(self):
        return self.title


class VisitRecord(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_visit_records",
    )
    # 대상은 공식 event와 비공식 personal_entry 중 정확히 하나여야 한다.
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="archive_user_visit_records",
        null=True,
        blank=True,
    )
    personal_entry = models.ForeignKey(
        PersonalEntry,
        on_delete=models.CASCADE,
        related_name="archive_user_visit_records",
        null=True,
        blank=True,
    )
    visited_on = models.DateField()
    short_review = models.CharField(max_length=255, blank=True)
    # bfcache 재생 등으로 같은 요청이 중복 전송돼도 한 번만 처리되도록
    # 클라이언트가 발급하는 멱등 키. 사용자가 직접 수정할 수 없고, 이
    # 필드가 생기기 전에 만들어진 행은 비어 있다(null).
    client_token = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="visitrecord_exactly_one_subject",
                condition=(
                    models.Q(event__isnull=False, personal_entry__isnull=True)
                    | models.Q(event__isnull=True, personal_entry__isnull=False)
                ),
            ),
            models.UniqueConstraint(
                fields=["user", "client_token"],
                condition=models.Q(client_token__isnull=False),
                name="unique_archive_visit_record_user_client_token",
            ),
        ]


class VisitRecordPhoto(models.Model):
    visit_record = models.ForeignKey(
        VisitRecord,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="visit-record-photos/")
    # 멱등 키를 (user, client_token)이 아니라 (visit_record, client_token)로
    # 잡는다. 사진은 사용자 소유 최상위 대상이 아니라 한 방문 기록의
    # 하위 항목이고, 한 사용자가 여러 기록에 걸쳐 많은 사진을 올리므로
    # 중복 방지 키는 기록 단위여야 한다.
    client_token = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["visit_record", "client_token"],
                condition=models.Q(client_token__isnull=False),
                name="unique_archive_visit_record_photo_visit_record_client_token",
            ),
        ]


class CollectionItem(models.Model):
    """사용자 소유의 굿즈 컬렉션 항목.

    항상 소유자 본인에게만 비공개이며, event/visit_record는 어떻게
    입수했는지를 가리키는 선택적 링크일 뿐이다.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_collection_items",
    )
    name = models.CharField(max_length=255)
    work_title = models.CharField(max_length=255, blank=True)
    character_name = models.CharField(max_length=255, blank=True)
    # 자유 입력 항목이다. core.vocab.COLLECTION_ITEM_TYPE의 어휘 목록은
    # UI 안내용일 뿐 DB choices 제약이 아니다.
    item_type = models.CharField(max_length=100, blank=True)
    quantity = models.IntegerField(default=1)
    acquired_on = models.DateField(null=True, blank=True)
    acquisition_source = models.CharField(max_length=100, blank=True)
    # SET_NULL: 상위 event가 완전 삭제돼도 사용자의 컬렉션 항목이 조용히
    # 함께 사라지면 안 된다.
    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        related_name="archive_collection_items",
        null=True,
        blank=True,
    )
    # SET_NULL: 위 event와 같은 이유(데이터 유실 방지)로 지정한다.
    visit_record = models.ForeignKey(
        VisitRecord,
        on_delete=models.SET_NULL,
        related_name="archive_collection_items",
        null=True,
        blank=True,
    )
    image = models.ImageField(upload_to="collection-items/", blank=True, null=True)
    memo = models.TextField(blank=True)
    is_wanted = models.BooleanField(default=False)
    tradeable_quantity = models.IntegerField(default=0)
    # 추후 교환 옵트인 게이트를 위해 남겨둔 필드다. 그 단계가 승인되기
    # 전까지는 어디에도 노출하지 않는다.
    visibility = models.CharField(max_length=20, default="private")
    # bfcache 재생 등으로 같은 요청이 중복 전송돼도 한 번만 처리되도록
    # 클라이언트가 발급하는 멱등 키. 사용자가 직접 수정할 수 없고, 이
    # 필드가 생기기 전에 만들어진 행은 비어 있다(null).
    client_token = models.UUIDField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="collectionitem_quantity_gte_0",
                condition=models.Q(quantity__gte=0),
            ),
            models.CheckConstraint(
                name="collectionitem_tradeable_lte_quantity",
                condition=models.Q(tradeable_quantity__lte=models.F("quantity")),
            ),
            models.CheckConstraint(
                name="collectionitem_tradeable_gte_0",
                condition=models.Q(tradeable_quantity__gte=0),
            ),
            models.UniqueConstraint(
                fields=["user", "client_token"],
                condition=models.Q(client_token__isnull=False),
                name="unique_archive_collection_item_user_client_token",
            ),
        ]
        # 소유자별 work_title/character_name/item_type 필터 조회가 매번
        # 테이블 전체를 스캔하지 않도록 지원한다.
        indexes = [
            models.Index(fields=["user", "work_title"], name="collectionitem_user_work_idx"),
            models.Index(fields=["user", "character_name"], name="collectionitem_user_char_idx"),
            models.Index(fields=["user", "item_type"], name="collectionitem_user_type_idx"),
        ]

    def clean(self):
        super().clean()
        # visit_record는 다른 테이블을 참조하므로 DB CheckConstraint로는
        # 강제할 수 없다. create_collection_item의 서비스 단 동기화에 더해
        # 여기서 2차로 방어한다.
        if (
            self.visit_record_id is not None
            and self.event_id is not None
            and self.visit_record.event_id != self.event_id
        ):
            raise ValidationError(
                "event must match visit_record.event when both are set."
            )


class ActivityLogEntry(models.Model):
    """사용자의 컬렉션·방문 활동을 달력용으로 기록한다.

    반드시 해당 활동을 처리하는 서비스 함수가 같은 트랜잭션 안에서
    직접 기록한다. 시그널로 기록하지 않는다.
    """

    class Kind(models.TextChoices):
        INTEREST_ADDED = "interest_added", "Interest added"
        INTEREST_REMOVED = "interest_removed", "Interest removed"
        STATUS_CHANGED = "status_changed", "Status changed"
        STATUS_REMOVED = "status_removed", "Status removed"
        VISIT_RECORD_CREATED = "visit_record_created", "Visit record created"
        COLLECTION_ITEM_CREATED = "collection_item_created", "Collection item created"
        COLLECTION_ITEM_ORGANIZED = "collection_item_organized", "Collection item organized"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_activity_log_entries",
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    occurred_at = models.DateTimeField()
    # 아래 각 FK는 이 기록이 무엇을 가리키는지에 대한 선택적 포인터일 뿐,
    # 위 EventInterest/UserEventStatus/VisitRecord처럼 "정확히 하나"를
    # 강제하는 쌍이 아니라서 여기엔 그런 CheckConstraint가 없다.
    # SET_NULL: 상위 행이 완전 삭제돼도 달력 이력이 조용히 사라지면
    # 안 된다. FK가 사라진 뒤엔 subject_label이 그 자리를 대신한다.
    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        related_name="archive_activity_log_entries",
        null=True,
        blank=True,
    )
    visit_record = models.ForeignKey(
        VisitRecord,
        on_delete=models.SET_NULL,
        related_name="activity_log_entries",
        null=True,
        blank=True,
    )
    collection_item = models.ForeignKey(
        CollectionItem,
        on_delete=models.SET_NULL,
        related_name="activity_log_entries",
        null=True,
        blank=True,
    )
    subject_label = models.CharField(max_length=255)
    change_summary = models.JSONField(default=dict, blank=True)
    # VisitRecord/CollectionItem의 client_token과 같은 취지의 멱등 키다.
    # (user,) 단독이 아니라 (user, kind)로 스코프한 이유는, 하나의
    # client_token(예: VisitRecord 생성)이 여러 종류의 기록으로 나뉘어
    # 기록될 수 있기 때문이다.
    operation_key = models.UUIDField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind", "operation_key"],
                condition=models.Q(operation_key__isnull=False),
                name="unique_archive_activity_log_entry_user_kind_operation_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "occurred_at"], name="archive_actlog_user_occ_idx"
            ),
        ]
