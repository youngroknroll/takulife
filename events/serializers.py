from rest_framework import serializers

from .models import Event, UserEventStatus, VisitRecord, VisitRecordPhoto


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "publish_status"]


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
