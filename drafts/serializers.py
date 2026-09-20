from rest_framework import serializers

from .models import EventDraft


class DiscoveryRunnerLiveSerializer(serializers.Serializer):
    """drafts.queries.runner_live_summary()의 8키를 그대로 옮긴다."""

    online = serializers.BooleanField()
    phase = serializers.CharField()
    phase_label = serializers.CharField()
    detail = serializers.CharField()
    progress_visible = serializers.BooleanField()
    current_run_id = serializers.IntegerField(allow_null=True)
    last_heartbeat_at = serializers.DateTimeField(allow_null=True)
    active = serializers.BooleanField()


class DiscoveryRunOutcomeSerializer(serializers.Serializer):
    """drafts.queries._outcome_rows() 항목 하나를 옮긴다."""

    display_url = serializers.CharField()
    outcome = serializers.CharField()
    outcome_label = serializers.CharField()
    tone = serializers.CharField()
    reason_label = serializers.CharField(allow_blank=True)


class DiscoveryRunSummarySerializer(serializers.Serializer):
    """drafts.queries.recent_discovery_runs()가 만든 행 하나(run 객체 +
    집계 키)를 대시보드 폴링 응답 형태로 옮긴다."""

    id = serializers.IntegerField(source="run.id")
    status = serializers.CharField(source="run.status")
    status_label = serializers.CharField()
    tone = serializers.CharField()
    query = serializers.CharField(source="run.query")
    created_at = serializers.DateTimeField(source="run.created_at")
    promoted_count = serializers.IntegerField()
    failed_count = serializers.IntegerField()
    events_created = serializers.IntegerField()
    events_excluded = serializers.IntegerField(allow_null=True)
    events_failed = serializers.IntegerField(allow_null=True)
    error_summary = serializers.CharField(source="run.error_summary", allow_blank=True)
    outcomes = DiscoveryRunOutcomeSerializer(many=True, source="outcome_rows")


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
            "extraction_method",
            "confidence",
            "review_status",
            "created_at",
            "updated_at",
            "reviewed_by",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "reopened_at",
            "origin",
            "intake_note",
            "discovery_run",
        ]
        read_only_fields = [
            "extraction_method",
            "confidence",
            "review_status",
            "created_at",
            "updated_at",
            "reviewed_by",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "reopened_at",
            "origin",
            "intake_note",
            "discovery_run",
        ]

    def validate_source_url(self, value):
        if not value.startswith(("http://", "https://")):
            raise serializers.ValidationError("Only HTTP and HTTPS URLs are supported.")
        return value


class EventDraftUpdateSerializer(EventDraftSerializer):
    immutable_fields = (
        "source_url",
        "raw_title",
        "raw_text",
        "review_status",
        "extraction_method",
        "confidence",
        "intake_note",
        "discovery_run",
    )

    class Meta(EventDraftSerializer.Meta):
        read_only_fields = [
            "id",
            "source_url",
            "raw_title",
            "raw_text",
            "review_status",
            "extraction_method",
            "confidence",
            "created_at",
            "updated_at",
            "reviewed_by",
            "approved_at",
            "rejected_at",
            "rejection_reason",
            "reopened_at",
            "origin",
            "intake_note",
            "discovery_run",
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
