from rest_framework import serializers

from .models import EventDraft


class EventDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventDraft
        fields = [
            "id",
            "source_url",
            "source_name",
            "raw_title",
            "raw_text",
            "extracted_title",
            "extracted_category",
            "extracted_work_title",
            "extracted_location_name",
            "extracted_region",
            "extracted_start_date",
            "extracted_end_date",
            "extracted_summary",
            "review_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["review_status", "created_at", "updated_at"]

    def validate_source_url(self, value):
        if not value.startswith(("http://", "https://")):
            raise serializers.ValidationError("Only HTTP and HTTPS URLs are supported.")
        return value


class EventDraftUpdateSerializer(EventDraftSerializer):
    immutable_fields = ("source_url", "raw_title", "raw_text")

    class Meta(EventDraftSerializer.Meta):
        read_only_fields = [
            "id",
            "source_url",
            "raw_title",
            "raw_text",
            "review_status",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        errors = {
            field: ["This field cannot be updated."]
            for field in self.immutable_fields
            if field in self.initial_data
        }
        if errors:
            raise serializers.ValidationError(errors)
        return super().validate(attrs)
