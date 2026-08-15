from rest_framework import serializers

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
    # "all"은 with_public_status에 별도 분기가 없어 필터 없음과 동일하게 동작한다.
    STATUS_CHOICES = ("upcoming", "ongoing", "closing_soon", "ended", "all")
    SORT_CHOICES = ("closing_soon", "start_asc", "newest")

    q = serializers.CharField(required=False, allow_blank=True)
    # region/category는 다중값이다: ?region=seoul&region=gyeonggi → OR 필터.
    region = serializers.ListField(child=serializers.CharField(), required=False)
    category = serializers.ListField(child=serializers.CharField(), required=False)
    work_title = serializers.CharField(required=False, allow_blank=True)
    start_date_from = serializers.DateField(required=False)
    start_date_to = serializers.DateField(required=False)
    status = serializers.ChoiceField(required=False, choices=STATUS_CHOICES)
    sort = serializers.ChoiceField(required=False, choices=SORT_CHOICES)
