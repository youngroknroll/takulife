from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)
from .queries import list_user_personal_entries
from .serializers import (
    EventInterestSerializer,
    PersonalEntrySerializer,
    UserEventStatusQuerySerializer,
    UserEventStatusSerializer,
    UserEventStatusUpdateSerializer,
    VisitRecordPhotoUploadSerializer,
    VisitRecordSerializer,
)
from .services import (
    DuplicateEventInterestError,
    DuplicateUserEventStatusError,
    PhotoLimitExceededError,
    create_event_interest,
    create_personal_entry,
    create_user_event_status,
    create_visit_record,
    create_visit_record_photo,
    mark_missed,
    mark_visited,
    revert_to_planned,
)


class PersonalEntryPagination(PageNumberPagination):
    page_size = 20


class PersonalEntryListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PersonalEntrySerializer
    pagination_class = PersonalEntryPagination

    def get_queryset(self):
        return list_user_personal_entries(self.request.user)

    def perform_create(self, serializer):
        # owner is the requester, never the payload
        serializer.instance = create_personal_entry(
            user=self.request.user, **serializer.validated_data
        )


class PersonalEntryDetailView(RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PersonalEntrySerializer

    def get_queryset(self):
        return PersonalEntry.objects.filter(user=self.request.user)


class EventInterestPagination(PageNumberPagination):
    page_size = 20


class EventInterestListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EventInterestSerializer
    pagination_class = EventInterestPagination

    def get_queryset(self):
        return EventInterest.objects.filter(user=self.request.user).order_by("-id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            interest = create_event_interest(
                user=request.user,
                event=serializer.validated_data.get("event"),
                personal_entry=serializer.validated_data.get("personal_entry"),
            )
        except DuplicateEventInterestError:
            return Response(
                {
                    "code": "duplicate_event_interest",
                    "detail": "Event interest already exists for this event.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        response_serializer = self.get_serializer(interest)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class EventInterestDetailView(RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EventInterestSerializer

    def get_queryset(self):
        return EventInterest.objects.filter(user=self.request.user)


class UserEventStatusPagination(PageNumberPagination):
    page_size = 20


class UserEventStatusListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserEventStatusSerializer
    pagination_class = UserEventStatusPagination

    def _validated_query_params(self):
        serializer = UserEventStatusQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def get_queryset(self):
        params = self._validated_query_params()
        queryset = UserEventStatus.objects.filter(user=self.request.user)
        if "event" in params:
            queryset = queryset.filter(event_id=params["event"])
        if "status" in params:
            queryset = queryset.filter(status=params["status"])
        return queryset.order_by("id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            status_object = create_user_event_status(
                user=request.user,
                event=serializer.validated_data.get("event"),
                personal_entry=serializer.validated_data.get("personal_entry"),
                status=serializer.validated_data["status"],
            )
        except DuplicateUserEventStatusError:
            return Response(
                {
                    "code": "duplicate_user_event_status",
                    "detail": "User event status already exists for this event.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        response_serializer = self.get_serializer(status_object)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class UserEventStatusDetailView(RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated]

    # Each target status owns a distinct transition (visited/missed leave the
    # opt-out flag; planned pins it). Routing here keeps the state-transition
    # rule in the service layer instead of a blind serializer.save().
    _TRANSITIONS = {
        UserEventStatus.Status.VISITED: mark_visited,
        UserEventStatus.Status.MISSED: mark_missed,
        UserEventStatus.Status.PLANNED: revert_to_planned,
    }

    def get_queryset(self):
        return UserEventStatus.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserEventStatusUpdateSerializer
        return UserEventStatusSerializer

    def perform_update(self, serializer):
        target = serializer.validated_data.get("status")
        transition = self._TRANSITIONS.get(target)
        if transition is None:
            serializer.save()
            return
        transition(user_event_status=serializer.instance)


class VisitRecordPagination(PageNumberPagination):
    page_size = 20


class VisitRecordListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VisitRecordSerializer
    pagination_class = VisitRecordPagination

    def get_queryset(self):
        return (
            VisitRecord.objects.filter(user=self.request.user)
            .order_by("-visited_on", "-id")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = create_visit_record(
            user=request.user,
            event=serializer.validated_data.get("event"),
            personal_entry=serializer.validated_data.get("personal_entry"),
            visited_on=serializer.validated_data["visited_on"],
            short_review=serializer.validated_data.get("short_review", ""),
        )
        response_serializer = self.get_serializer(record)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class VisitRecordDetailView(RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VisitRecordSerializer

    def get_queryset(self):
        return VisitRecord.objects.filter(user=self.request.user)


class VisitRecordPhotoCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, record_id):
        record = get_object_or_404(VisitRecord, pk=record_id, user=request.user)
        serializer = VisitRecordPhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            photo = create_visit_record_photo(
                visit_record=record,
                image=serializer.validated_data["image"],
            )
        except PhotoLimitExceededError:
            return Response(
                {
                    "code": "photo_limit_exceeded",
                    "detail": "A visit record can have at most 10 photos.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"id": photo.id, "visit_record": record.id}, status=status.HTTP_201_CREATED)


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
