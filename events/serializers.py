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
    # "all" has no branch in with_public_status; it falls through to the
    # catch-all and behaves the same as an unset status (no filtering).
    STATUS_CHOICES = ("upcoming", "ongoing", "closing_soon", "ended", "all")
    SORT_CHOICES = ("closing_soon", "start_asc", "newest")

    q = serializers.CharField(required=False, allow_blank=True)
    # region/category are multi-value: ?region=seoul&region=gyeonggi → OR filter.
    # The parser normalises a single value into a 1-element list before validation.
    region = serializers.ListField(child=serializers.CharField(), required=False)
    category = serializers.ListField(child=serializers.CharField(), required=False)
    work_title = serializers.CharField(required=False, allow_blank=True)
    start_date_from = serializers.DateField(required=False)
    start_date_to = serializers.DateField(required=False)
    status = serializers.ChoiceField(required=False, choices=STATUS_CHOICES)
    sort = serializers.ChoiceField(required=False, choices=SORT_CHOICES)


class EventPosterUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)

    def validate_image(self, value):
        return validate_uploaded_image(value)
