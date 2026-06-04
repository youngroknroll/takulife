from rest_framework import serializers

from .models import Event, UserEventStatus, VisitRecord, VisitRecordPhoto


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "category",
            "work_title",
            "location_name",
            "region",
            "start_date",
            "end_date",
            "official_url",
            "source_name",
            "summary",
        ]


class EventQuerySerializer(serializers.Serializer):
    STATUS_CHOICES = ("upcoming", "ongoing", "closing_soon", "ended")

    q = serializers.CharField(required=False, allow_blank=True)
    region = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    work_title = serializers.CharField(required=False, allow_blank=True)
    start_date_from = serializers.DateField(required=False)
    start_date_to = serializers.DateField(required=False)
    status = serializers.ChoiceField(required=False, choices=STATUS_CHOICES)


class UserEventStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserEventStatus
        fields = ["event", "status"]


class VisitRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitRecord
        fields = ["id", "event", "visited_on", "short_review"]


class VisitRecordPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitRecordPhoto
        fields = ["id", "image", "visit_record"]
