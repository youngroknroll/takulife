from rest_framework import serializers

from .image_validation import validate_uploaded_image
from .models import Event


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


class EventPosterUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)

    def validate_image(self, value):
        return validate_uploaded_image(value)
