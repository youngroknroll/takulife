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
    # Client-supplied idempotency key (bfcache duplicate-creation plan §4-1).
    # write_only so a replayed create's token is never echoed back.
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
        # owner is taken from the request, never the payload
        read_only_fields = ["id", "created_at"]

    def validate_image(self, value):
        # Route the optional image through the shared guard (size, extension,
        # real format, per-axis dimension, and total pixel-area decompression
        # -bomb caps) — the same protection visit photos already get. DRF's
        # default ImageField only confirms it decodes, not that it is safe.
        if value in (None, ""):
            return value
        return validate_uploaded_image(value)


class PersonalEntryUpdateSerializer(PersonalEntrySerializer):
    """PATCH serializer: identical to `PersonalEntrySerializer` except
    `client_token` is structurally excluded — a create-time idempotency key
    must never be re-read or overwritten on update.
    """

    client_token = None

    class Meta(PersonalEntrySerializer.Meta):
        fields = [field for field in PersonalEntrySerializer.Meta.fields if field != "client_token"]


class _SubjectScopedPersonalEntryMixin:
    """Scopes the ``personal_entry`` field to the requester and enforces that
    exactly one subject (event or personal_entry) is supplied.

    Shared by the interest/status serializers so an archive action can point at
    an official Event OR the user's own unofficial PersonalEntry — never both,
    never neither, and never another user's private item.
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
    # subject = exactly one of event (published) or personal_entry (own).
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
    # subject = exactly one of event (published) or personal_entry (own).
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


class UserEventStatusQuerySerializer(serializers.Serializer):
    event = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(required=False, choices=UserEventStatus.Status.choices)


class VisitRecordSerializer(serializers.ModelSerializer):
    # subject = exactly one of event (published) or personal_entry (own).
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(), required=False, allow_null=True
    )
    personal_entry = serializers.PrimaryKeyRelatedField(
        queryset=PersonalEntry.objects.none(), required=False, allow_null=True
    )
    # Client-supplied idempotency key (bfcache duplicate-creation plan §4-1).
    # write_only so a replayed create's token is never echoed back.
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
        # Scope personal_entry to the requester so you can't attach to someone
        # else's private item.
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
    """PATCH serializer: only visited_on / short_review are editable; the
    subject (event / personal_entry) stays pinned to the original record."""

    class Meta:
        model = VisitRecord
        fields = ["id", "event", "personal_entry", "visited_on", "short_review"]
        read_only_fields = ["id", "event", "personal_entry"]


class VisitRecordPhotoUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    # Client-supplied idempotency key (bfcache duplicate-creation plan §4-1),
    # scoped by (visit_record, client_token) — see VisitRecordPhoto's
    # UniqueConstraint. write_only so a replayed create's token is never
    # echoed back.
    client_token = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    def validate_image(self, value):
        # Delegate to the shared validator (size, extension, real format, per-axis
        # dimension, and total pixel-area decompression-bomb guards).
        return validate_uploaded_image(value)


class CollectionItemSerializer(serializers.ModelSerializer):
    """Owner is always taken from the request, never the payload.
    `visibility` is deliberately absent from `fields` (not read_only) —
    reserved for the future trade opt-in gate, no exposure until Stage 4
    (collection domain design plan §3-1, PO decision 2026-07-16). Create-only
    (see `CollectionItemUpdateSerializer` for PATCH): `client_token` is a
    create-time idempotency key and must not leak into the update path
    (bfcache duplicate-creation plan, DAR mandatory fix ③). No fields are
    pinned read-only besides id/created_at/updated_at because, unlike
    VisitRecord/UserEventStatus, a CollectionItem's event/visit_record links
    are themselves user-editable after creation.
    """

    # event is scoped to published events only (same guard as
    # VisitRecordSerializer/UserEventStatusSerializer).
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(), required=False, allow_null=True
    )
    visit_record = serializers.PrimaryKeyRelatedField(
        queryset=VisitRecord.objects.all(), required=False, allow_null=True
    )
    # Client-supplied idempotency key (bfcache duplicate-creation plan §4-1).
    # write_only so a replayed create's token is never echoed back.
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
        # Scope visit_record to the requester (mirrors
        # _SubjectScopedPersonalEntryMixin/VisitRecordSerializer's
        # personal_entry scoping). Without this, a cross-user visit_record id
        # reaches create_collection_item/update_collection_item's ownership
        # guard, whose distinct error message makes the field an existence
        # oracle for VisitRecord ids system-wide (security gate M1,
        # 2026-07-16) — attachment could never succeed either way, but the
        # two failure messages were distinguishable. The service-level
        # ownership guard stays in place as defense in depth.
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["visit_record"].queryset = VisitRecord.objects.filter(
                user=request.user
            )

    def validate_image(self, value):
        # Route the optional image through the shared guard, mirroring
        # PersonalEntrySerializer.validate_image.
        if value in (None, ""):
            return value
        return validate_uploaded_image(value)


class CollectionItemUpdateSerializer(CollectionItemSerializer):
    """PATCH serializer: identical to `CollectionItemSerializer` except
    `client_token` is structurally excluded — a create-time idempotency key
    must never be re-read or overwritten on update (DAR mandatory fix ③).
    Inherits visit_record scoping (__init__) and validate_image unchanged.
    """

    client_token = None

    class Meta(CollectionItemSerializer.Meta):
        fields = [field for field in CollectionItemSerializer.Meta.fields if field != "client_token"]


class CollectionItemQuerySerializer(serializers.Serializer):
    """Validates CollectionItem list query params before they reach
    list_user_collection_items (mirrors UserEventStatusQuerySerializer).

    `duplicate`/`tradeable`/`owned` are booleans selecting the *derived*
    condition (quantity >= 2 / tradeable_quantity > 0 / quantity > 0) — the
    query layer owns the actual filter logic, this serializer only validates
    shape.

    Empty-value contract (domain gate finding, 2026-07-16): an *absent*
    param and an *empty* param (`?work_title=`) both mean "no filter" —
    uniform across all six filters so a client can naively serialize a form
    without per-field blank-stripping. `max_length` mirrors the model's own
    CharField caps (security gate L4). Genuinely invalid values (e.g.
    `?is_wanted=ture`) still 400 — only emptiness is tolerated.
    """

    work_title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    character_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    item_type = serializers.CharField(required=False, allow_blank=True, max_length=100)
    is_wanted = serializers.BooleanField(required=False, allow_null=True)
    duplicate = serializers.BooleanField(required=False, allow_null=True)
    tradeable = serializers.BooleanField(required=False, allow_null=True)
    owned = serializers.BooleanField(required=False, allow_null=True)
