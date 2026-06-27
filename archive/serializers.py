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
        return attrs


class VisitRecordPhotoUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)

    def validate_image(self, value):
        # Delegate to the shared validator (size, extension, real format, per-axis
        # dimension, and total pixel-area decompression-bomb guards).
        return validate_uploaded_image(value)
