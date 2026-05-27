from rest_framework import serializers

from .models import EventDraft


class EventDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventDraft
        fields = ["id", "source_url", "review_status"]
