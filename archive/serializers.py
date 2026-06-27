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


class EventInterestSerializer(serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(),
    )

    class Meta:
        model = EventInterest
        fields = ["id", "event"]
        read_only_fields = ["id"]


class UserEventStatusSerializer(serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(),
    )

    class Meta:
        model = UserEventStatus
        fields = ["id", "event", "status"]
        read_only_fields = ["id"]


class UserEventStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserEventStatus
        fields = ["id", "event", "status"]
        read_only_fields = ["id", "event"]


class UserEventStatusQuerySerializer(serializers.Serializer):
    event = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(required=False, choices=UserEventStatus.Status.choices)


class VisitRecordSerializer(serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.published(),
    )

    class Meta:
        model = VisitRecord
        fields = ["id", "event", "visited_on", "short_review"]
        read_only_fields = ["id"]


class VisitRecordPhotoUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)

    def validate_image(self, value):
        # Delegate to the shared validator (size, extension, real format, per-axis
        # dimension, and total pixel-area decompression-bomb guards).
        return validate_uploaded_image(value)
