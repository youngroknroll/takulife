from rest_framework import serializers

from events.models import Event

from .models import UserEventStatus


class UserEventStatusSerializer(serializers.ModelSerializer):
    event = serializers.PrimaryKeyRelatedField(
        queryset=Event.objects.filter(publish_status=Event.PublishStatus.PUBLISHED),
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
