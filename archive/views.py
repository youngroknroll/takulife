from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    UserEventStatusQuerySerializer,
    UserEventStatusSerializer,
    UserEventStatusUpdateSerializer,
)
from .services import DuplicateUserEventStatusError, create_user_event_status
from .models import UserEventStatus


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
            status_object = create_user_event_status(user=request.user, serializer=serializer)
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

    def get_queryset(self):
        return UserEventStatus.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserEventStatusUpdateSerializer
        return UserEventStatusSerializer
