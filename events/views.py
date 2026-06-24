from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Event, UserEventStatus, VisitRecord, VisitRecordPhoto
from .queries import PUBLIC_LISTING_PAGE_SIZE, list_published_events, parse_public_listing_params
from .serializers import (
    EventSerializer,
    UserEventStatusSerializer,
    VisitRecordPhotoSerializer,
    VisitRecordSerializer,
)


class EventPagination(PageNumberPagination):
    page_size = PUBLIC_LISTING_PAGE_SIZE


class PublicEventListView(ListAPIView):
    serializer_class = EventSerializer
    pagination_class = EventPagination

    def get_queryset(self):
        params = parse_public_listing_params(self.request.query_params)
        return list_published_events(params)


class PublicEventDetailView(RetrieveAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.published()


class UserEventStatusUpsertView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, event_id):
        event = get_object_or_404(
            Event.objects.published(),
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
            Event.objects.published(),
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
