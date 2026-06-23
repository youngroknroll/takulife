from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Event, UserEventStatus, VisitRecord, VisitRecordPhoto
from .serializers import (
    EventQuerySerializer,
    EventSerializer,
    UserEventStatusSerializer,
    VisitRecordPhotoSerializer,
    VisitRecordSerializer,
)


class EventPagination(PageNumberPagination):
    page_size = 20


class PublicEventListView(ListAPIView):
    serializer_class = EventSerializer
    pagination_class = EventPagination
    query_serializer_class = EventQuerySerializer

    def _validated_query_params(self):
        allowed_fields = self.query_serializer_class().fields
        data = {
            key: value
            for key, value in self.request.query_params.items()
            if key in allowed_fields
        }
        serializer = self.query_serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def get_queryset(self):
        params = self._validated_query_params()
        today = timezone.localdate()
        return (
            Event.objects.published()
            .filter_for_public_listing(params, today=today)
            .order_for_public_listing(today=today)
        )


class PublicEventDetailView(RetrieveAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.published()


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
