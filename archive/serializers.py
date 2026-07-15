from rest_framework import serializers

from events.image_validation import validate_uploaded_image
from events.models import Event

from .models import (
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)


class PersonalEntrySerializer(serializers.ModelSerializer):
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

    def validate_kind(self, value):
        # PersonalEntry is restricted to unofficial places (collection domain
        # design plan §3-3) — goods are moving to the dedicated CollectionItem
        # domain and can no longer be created here.
        if value != PersonalEntry.Kind.PLACE:
            raise serializers.ValidationError(
                "goods는 더 이상 PersonalEntry로 생성할 수 없습니다."
            )
        return value


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
                "goods personal_entry는 이 작업의 대상이 될 수 없습니다."
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

    class Meta:
        model = VisitRecord
        fields = ["id", "event", "personal_entry", "visited_on", "short_review"]
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
                "goods personal_entry는 이 작업의 대상이 될 수 없습니다."
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

    def validate_image(self, value):
        # Delegate to the shared validator (size, extension, real format, per-axis
        # dimension, and total pixel-area decompression-bomb guards).
        return validate_uploaded_image(value)
