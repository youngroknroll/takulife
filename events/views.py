from datetime import date

from django.db.models import Case, DateField, F, IntegerField, Value, When
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Event, UserEventStatus, VisitRecord, VisitRecordPhoto
from .serializers import EventSerializer, UserEventStatusSerializer, VisitRecordPhotoSerializer, VisitRecordSerializer


class EventPagination(PageNumberPagination):
    page_size = 20


class PublicEventListView(ListAPIView):
    serializer_class = EventSerializer
    pagination_class = EventPagination

    def get_queryset(self):
        queryset = Event.objects.filter(publish_status=Event.PublishStatus.PUBLISHED)
        query = self.request.query_params.get("q")
        if query:
            queryset = queryset.filter(title__icontains=query)
        region = self.request.query_params.get("region")
        if region:
            queryset = queryset.filter(region=region)
        category = self.request.query_params.get("category")
        if not category:
            category = self.request.query_params.get("event_type")
        if category:
            queryset = queryset.filter(category=category)
        work_title = self.request.query_params.get("work_title")
        if work_title:
            queryset = queryset.filter(work_title__icontains=work_title)
        start_date_from = self._get_query_value("start_date_from", "starts_after")
        if start_date_from:
            parsed_from = self._parse_date(start_date_from)
            if parsed_from:
                queryset = queryset.filter(start_date__gte=parsed_from)
        start_date_to = self._get_query_value("start_date_to", "starts_before")
        if start_date_to:
            parsed_to = self._parse_date(start_date_to)
            if parsed_to:
                queryset = queryset.filter(start_date__lte=parsed_to)
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = self._filter_by_status(queryset, status_param)
        return self._order_default(queryset)

    def _get_query_value(self, primary_name, alias_name):
        value = self.request.query_params.get(primary_name)
        if value:
            return value
        return self.request.query_params.get(alias_name)

    @staticmethod
    def _parse_date(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _filter_by_status(self, queryset, status_param):
        today = date.today()
        if status_param == "upcoming":
            return queryset.filter(start_date__gt=today)
        if status_param == "ongoing":
            return queryset.filter(start_date__lte=today).filter(end_date__gte=today)
        if status_param == "ended":
            return queryset.filter(end_date__lt=today)
        return queryset

    def _order_default(self, queryset):
        today = date.today()
        return queryset.annotate(
            _state_rank=Case(
                When(start_date__lte=today, end_date__gte=today, then=Value(0)),
                When(start_date__gt=today, then=Value(1)),
                When(end_date__lt=today, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            _ongoing_sort=Case(
                When(start_date__lte=today, end_date__gte=today, then=F("end_date")),
                output_field=DateField(),
            ),
            _upcoming_sort=Case(
                When(start_date__gt=today, then=F("start_date")),
                output_field=DateField(),
            ),
            _ended_sort=Case(
                When(end_date__lt=today, then=F("end_date")),
                output_field=DateField(),
            ),
        ).order_by("_state_rank", "_ongoing_sort", "_upcoming_sort", F("_ended_sort").desc(), "id")


class PublicEventDetailView(RetrieveAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.filter(publish_status=Event.PublishStatus.PUBLISHED)


class UserEventStatusUpsertView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, event_id):
        event = get_object_or_404(
            Event.objects.filter(publish_status=Event.PublishStatus.PUBLISHED),
            pk=event_id,
        )
        status_value = request.data.get("status")
        status, created = UserEventStatus.objects.update_or_create(
            user=request.user,
            event=event,
            defaults={"status": status_value},
        )
        serializer = UserEventStatusSerializer(status)
        return Response(serializer.data, status=201 if created else 200)


class VisitRecordListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        event = get_object_or_404(
            Event.objects.filter(publish_status=Event.PublishStatus.PUBLISHED),
            pk=request.data.get("event"),
        )
        record = VisitRecord.objects.create(
            user=request.user,
            event=event,
            visited_on=request.data.get("visited_on"),
            short_review=request.data.get("short_review", ""),
        )
        serializer = VisitRecordSerializer(record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VisitRecordPhotoListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, record_id):
        record = get_object_or_404(VisitRecord, pk=record_id, user=request.user)
        photo = VisitRecordPhoto.objects.create(
            visit_record=record,
            image=request.FILES["image"],
        )
        serializer = VisitRecordPhotoSerializer(photo)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VisitRecordPhotoDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, record_id, photo_id):
        photo = get_object_or_404(
            VisitRecordPhoto.objects.select_related("visit_record"),
            pk=photo_id,
            visit_record_id=record_id,
            visit_record__user=request.user,
        )
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
