from rest_framework import serializers

from events.image_validation import validate_uploaded_image
from events.models import Event

from .models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)


class PersonalEntrySerializer(serializers.ModelSerializer):
    # 클라이언트가 발급하는 멱등 키. 재생된 생성 요청의 토큰이 응답에
    # 그대로 노출되지 않도록 write_only로 둔다.
    client_token = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = PersonalEntry
        fields = [
            "id",
            "kind",
            "title",
            "category",
            "work_title",
            "location_name",
            "region",
            "url",
            "memo",
            "image",
            "client_token",
            "created_at",
        ]
        # 소유자는 요청자 정보로 정하며 요청 본문 값은 쓰지 않는다.
        read_only_fields = ["id", "created_at"]

    def validate_image(self, value):
        # 방문 사진과 같은 공용 검증기로 보낸다(크기·확장자·실제 포맷·
        # 축별 치수·압축 폭탄 방지용 총 픽셀 상한). DRF 기본 ImageField는
        # 디코딩 가능 여부만 볼 뿐 안전한지는 보지 않는다.
        if value in (None, ""):
            return value
        return validate_uploaded_image(value)


class PersonalEntryUpdateSerializer(PersonalEntrySerializer):
    """`PersonalEntrySerializer`와 같되 `client_token`만 구조적으로
    뺀 PATCH용 시리얼라이저. 생성 시점 멱등 키는 수정 시 다시 읽거나
    덮어써서는 안 된다.
    """

    client_token = None

    class Meta(PersonalEntrySerializer.Meta):
        fields = [field for field in PersonalEntrySerializer.Meta.fields if field != "client_token"]


class _SubjectScopedPersonalEntryMixin:
    """``personal_entry`` 필드를 요청자 소유로 한정하고, event/personal_entry
    중 정확히 하나만 지정되도록 강제한다.

    관심/상태 시리얼라이저가 공유해서 사용한다. 이렇게 해야 공식 Event나
    사용자 본인의 비공식 PersonalEntry 중 하나만 가리킬 수 있고, 다른
    사용자의 비공개 항목은 절대 가리킬 수 없다.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["personal_entry"].queryset = PersonalEntry.objects.filter(
                user=request.user
            )

    def validate(self, attrs):
        event = attrs.get("event")
        personal_entry = attrs.get("personal_entry")
        if bool(event) == bool(personal_entry):
            raise serializers.ValidationError(
                "event 또는 personal_entry 중 정확히 하나를 지정해야 합니다."
            )
        if personal_entry is not None and personal_entry.kind != PersonalEntry.Kind.PLACE:
            raise serializers.ValidationError(
                "이 personal_entry는 이 작업의 대상이 될 수 없습니다."
            )
        return attrs


class EventInterestSerializer(_SubjectScopedPersonalEntryMixin, serializers.ModelSerializer):
    # 대상은 게시된 event와 본인 소유 personal_entry 중 정확히 하나여야 한다.
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(), required=False, allow_null=True
    )
    personal_entry = serializers.PrimaryKeyRelatedField(
        queryset=PersonalEntry.objects.none(), required=False, allow_null=True
    )

    class Meta:
        model = EventInterest
        fields = ["id", "event", "personal_entry"]
        read_only_fields = ["id"]


class UserEventStatusSerializer(_SubjectScopedPersonalEntryMixin, serializers.ModelSerializer):
    # 대상은 게시된 event와 본인 소유 personal_entry 중 정확히 하나여야 한다.
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(), required=False, allow_null=True
    )
    personal_entry = serializers.PrimaryKeyRelatedField(
        queryset=PersonalEntry.objects.none(), required=False, allow_null=True
    )

    class Meta:
        model = UserEventStatus
        fields = ["id", "event", "personal_entry", "status"]
        read_only_fields = ["id"]


class UserEventStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserEventStatus
        fields = ["id", "event", "personal_entry", "status"]
        read_only_fields = ["id", "event", "personal_entry"]

    def validate(self, attrs):
        # status는 read_only가 아니지만 부분 PATCH라 required=True만으로는
        # 누락을 걸러낼 수 없다(부분 업데이트는 필드별 required를 건너뛴다).
        if "status" not in attrs:
            raise serializers.ValidationError({"status": "상태를 지정해야 합니다."})
        return attrs


class UserEventStatusQuerySerializer(serializers.Serializer):
    event = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(required=False, choices=UserEventStatus.Status.choices)


class VisitRecordSerializer(serializers.ModelSerializer):
    # 대상은 게시된 event와 본인 소유 personal_entry 중 정확히 하나여야 한다.
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(), required=False, allow_null=True
    )
    personal_entry = serializers.PrimaryKeyRelatedField(
        queryset=PersonalEntry.objects.none(), required=False, allow_null=True
    )
    # 클라이언트가 발급하는 멱등 키. 재생된 생성 요청의 토큰이 응답에
    # 그대로 노출되지 않도록 write_only로 둔다.
    client_token = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = VisitRecord
        fields = [
            "id",
            "event",
            "personal_entry",
            "visited_on",
            "short_review",
            "client_token",
        ]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # personal_entry를 요청자 소유로 한정해 다른 사람의 비공개 항목에
        # 연결하지 못하게 한다.
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["personal_entry"].queryset = PersonalEntry.objects.filter(
                user=request.user
            )

    def validate(self, attrs):
        event = attrs.get("event")
        personal_entry = attrs.get("personal_entry")
        if bool(event) == bool(personal_entry):
            raise serializers.ValidationError(
                "event 또는 personal_entry 중 정확히 하나를 지정해야 합니다."
            )
        if personal_entry is not None and personal_entry.kind != PersonalEntry.Kind.PLACE:
            raise serializers.ValidationError(
                "이 personal_entry는 이 작업의 대상이 될 수 없습니다."
            )
        return attrs


class VisitRecordUpdateSerializer(serializers.ModelSerializer):
    """PATCH용: visited_on / short_review만 수정 가능하고, 대상
    (event / personal_entry)은 원본 기록에 고정된 채 바뀌지 않는다."""

    class Meta:
        model = VisitRecord
        fields = ["id", "event", "personal_entry", "visited_on", "short_review"]
        read_only_fields = ["id", "event", "personal_entry"]


class VisitRecordPhotoUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    # 클라이언트가 발급하는 멱등 키. (visit_record, client_token) 단위로
    # 스코프한다(VisitRecordPhoto의 UniqueConstraint 참고). 재생된 생성
    # 요청의 토큰이 응답에 그대로 노출되지 않도록 write_only로 둔다.
    client_token = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    def validate_image(self, value):
        # 공용 검증기로 위임한다(크기·확장자·실제 포맷·축별 치수·압축
        # 폭탄 방지용 총 픽셀 상한).
        return validate_uploaded_image(value)


class CollectionItemSerializer(serializers.ModelSerializer):
    """소유자는 항상 요청자 정보로 정하며 요청 본문 값은 쓰지 않는다.
    `visibility`는 `fields`에서 의도적으로 뺐다(read_only도 아님) — 추후
    교환 옵트인 게이트를 위해 남겨둔 것이고 그 단계가 승인되기 전까지는
    노출하지 않는다. 생성 전용(PATCH는 `CollectionItemUpdateSerializer`
    참고): `client_token`은 생성 시점 멱등 키라 수정 경로로 새어 들어가면
    안 된다. id/created_at/updated_at 외에는 읽기 전용으로 고정하지
    않는데, VisitRecord/UserEventStatus와 달리 CollectionItem의
    event/visit_record 링크는 생성 후에도 사용자가 직접 수정할 수 있기
    때문이다.
    """

    # event는 게시된 event로만 한정한다(VisitRecordSerializer/
    # UserEventStatusSerializer와 같은 보호 장치).
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(), required=False, allow_null=True
    )
    visit_record = serializers.PrimaryKeyRelatedField(
        queryset=VisitRecord.objects.all(), required=False, allow_null=True
    )
    # 클라이언트가 발급하는 멱등 키. 재생된 생성 요청의 토큰이 응답에
    # 그대로 노출되지 않도록 write_only로 둔다.
    client_token = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = CollectionItem
        fields = [
            "id",
            "name",
            "work_title",
            "character_name",
            "item_type",
            "quantity",
            "acquired_on",
            "acquisition_source",
            "event",
            "visit_record",
            "image",
            "memo",
            "is_wanted",
            "tradeable_quantity",
            "client_token",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # visit_record를 요청자 소유로 한정한다(personal_entry를 한정하는
        # _SubjectScopedPersonalEntryMixin/VisitRecordSerializer와 같은
        # 방식). 이게 없으면 다른 사용자의 visit_record id가
        # create_collection_item/update_collection_item의 소유권 검사까지
        # 도달하는데, 그 검사의 오류 메시지가 필드 값과 달라서 어떤
        # VisitRecord id가 실제로 존재하는지 알아낼 수 있는 통로가 된다.
        # 연결 자체는 어느 쪽이든 성공할 수 없지만 두 실패 메시지가
        # 구별됐다. 서비스 단 소유권 검사는 2차 방어로 그대로 둔다.
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["visit_record"].queryset = VisitRecord.objects.filter(
                user=request.user
            )

    def validate_image(self, value):
        # PersonalEntrySerializer.validate_image와 같은 방식으로 공용
        # 검증기로 보낸다.
        if value in (None, ""):
            return value
        return validate_uploaded_image(value)


class CollectionItemUpdateSerializer(CollectionItemSerializer):
    """`CollectionItemSerializer`와 같되 `client_token`만 구조적으로
    뺀 PATCH용 시리얼라이저. 생성 시점 멱등 키는 수정 시 다시 읽거나
    덮어써서는 안 된다. visit_record 한정(__init__)과 validate_image는
    그대로 물려받는다.
    """

    client_token = None

    class Meta(CollectionItemSerializer.Meta):
        fields = [field for field in CollectionItemSerializer.Meta.fields if field != "client_token"]


class CollectionItemQuerySerializer(serializers.Serializer):
    """CollectionItem 목록 조회 파라미터를 list_user_collection_items에
    닿기 전에 검증한다(UserEventStatusQuerySerializer와 같은 방식).

    `duplicate`/`tradeable`/`owned`는 파생 조건(수량>=2 / 교환가능수량>0 /
    수량>0)을 고르는 불리언이다 — 실제 필터 로직은 쿼리 계층이 갖고,
    이 시리얼라이저는 형태만 검증한다.

    파라미터가 아예 없는 경우와 빈 값(`?work_title=`)을 모두 "필터 없음"
    으로 취급한다. 여섯 필터 전부 동일하게 처리해야 클라이언트가 필드별
    공백 제거 없이 폼을 그대로 직렬화해 보낼 수 있다. `max_length`는
    모델 CharField의 최대 길이와 맞춘다. 값이 진짜로 잘못된 경우
    (예: `?is_wanted=ture`)는 여전히 400이며, 빈 값만 허용한다.
    """

    work_title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    character_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    item_type = serializers.CharField(required=False, allow_blank=True, max_length=100)
    is_wanted = serializers.BooleanField(required=False, allow_null=True)
    duplicate = serializers.BooleanField(required=False, allow_null=True)
    tradeable = serializers.BooleanField(required=False, allow_null=True)
    owned = serializers.BooleanField(required=False, allow_null=True)
