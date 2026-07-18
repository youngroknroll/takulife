from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)
from .queries import list_user_collection_items, list_user_personal_entries
from .serializers import (
    CollectionItemQuerySerializer,
    CollectionItemSerializer,
    CollectionItemUpdateSerializer,
    EventInterestSerializer,
    PersonalEntrySerializer,
    UserEventStatusQuerySerializer,
    UserEventStatusSerializer,
    UserEventStatusUpdateSerializer,
    VisitRecordPhotoUploadSerializer,
    VisitRecordSerializer,
    VisitRecordUpdateSerializer,
)
from .services import (
    MAX_PHOTOS_PER_RECORD,
    DuplicateEventInterestError,
    DuplicateUserEventStatusError,
    PhotoLimitExceededError,
    VisitRecordExistsError,
    complete_visit_with_record,
    create_collection_item,
    create_event_interest,
    create_personal_entry,
    create_user_event_status,
    create_visit_record_photo,
    mark_missed,
    mark_visited,
    revert_to_planned,
    update_collection_item,
    update_visit_record,
)


def _translate_domain_validation_error(exc):
    """Re-raise a service-layer django ValidationError as a DRF
    ValidationError, so archive.services invariant violations (e.g.
    CollectionItem quantity/FK-pair guards) surface as 400 responses
    instead of an unhandled 500 (collection domain design plan §4 PR-C5
    CP12/CP13 — DRF's exception handler does not translate
    django.core.exceptions.ValidationError on its own).
    """
    if hasattr(exc, "error_dict"):
        raise ValidationError(exc.message_dict)
    raise ValidationError(exc.messages)


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
        except VisitRecordExistsError:
            raise ValidationError(
                {"status": "이미 방문 기록이 있는 항목은 이 상태로 등록할 수 없습니다."}
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
        try:
            transition(user_event_status=serializer.instance)
        except VisitRecordExistsError:
            raise ValidationError(
                {"status": "이미 방문 기록이 있는 항목은 이 상태로 되돌릴 수 없습니다."}
            )


class VisitRecordPagination(PageNumberPagination):
    page_size = 20


class VisitRecordListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VisitRecordSerializer
    pagination_class = VisitRecordPagination
    throttle_scope = "visit_record_create"

    def get_throttles(self):
        # ScopedRateThrottle applies to the whole view, so scope it to the
        # write path only — a creation flood guard must not also throttle
        # the list (GET) path.
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        return (
            VisitRecord.objects.filter(user=self.request.user)
            .order_by("-visited_on", "-id")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = complete_visit_with_record(
            user=request.user,
            event=serializer.validated_data.get("event"),
            personal_entry=serializer.validated_data.get("personal_entry"),
            visited_on=serializer.validated_data["visited_on"],
            short_review=serializer.validated_data.get("short_review", ""),
            client_token=serializer.validated_data.get("client_token"),
        )
        response_serializer = self.get_serializer(record)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class VisitRecordDetailView(RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VisitRecord.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return VisitRecordUpdateSerializer
        return VisitRecordSerializer

    def perform_update(self, serializer):
        record = serializer.instance
        update_visit_record(
            record=record,
            visited_on=serializer.validated_data.get("visited_on", record.visited_on),
            short_review=serializer.validated_data.get(
                "short_review", record.short_review
            ),
        )


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
                    "detail": f"A visit record can have at most {MAX_PHOTOS_PER_RECORD} photos.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except VisitRecord.DoesNotExist:
            # The record existed at the ownership check above but was deleted
            # (e.g. by a concurrent request) before the service's
            # select_for_update().get(...) ran. Surface it as a normal 404
            # instead of a 500.
            raise Http404
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


class CollectionItemPagination(PageNumberPagination):
    page_size = 20


class CollectionItemListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CollectionItemSerializer
    pagination_class = CollectionItemPagination
    throttle_scope = "collection_item_create"

    def get_throttles(self):
        # ScopedRateThrottle applies to the whole view, so scope it to the
        # write path only — a creation flood guard must not also throttle
        # the list (GET) path.
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def _validated_query_params(self):
        # .dict() so DRF's BooleanField doesn't mistake the QueryDict for an
        # HTML form submission — for MultiValueDict-like inputs, an absent
        # optional BooleanField silently defaults to False instead of being
        # skipped (DRF's html.is_html_input heuristic), which would make an
        # un-set is_wanted/duplicate/tradeable filter wrongly narrow results.
        serializer = CollectionItemQuerySerializer(data=self.request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def get_queryset(self):
        return list_user_collection_items(self.request.user, **self._validated_query_params())

    def perform_create(self, serializer):
        # owner is the requester, never the payload
        try:
            serializer.instance = create_collection_item(
                user=self.request.user, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            _translate_domain_validation_error(exc)


class CollectionItemDetailView(RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CollectionItem.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CollectionItemUpdateSerializer
        return CollectionItemSerializer

    def perform_update(self, serializer):
        # update_collection_item re-fetches its own row under
        # select_for_update() (security gate M2) and returns that fresh
        # instance rather than mutating serializer.instance in place — the
        # response must be built from the returned object.
        try:
            serializer.instance = update_collection_item(
                item=serializer.instance, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            _translate_domain_validation_error(exc)
        except CollectionItem.DoesNotExist:
            # The item existed at this view's get_object() check above but
            # was deleted (e.g. by a concurrent request) before the
            # service's select_for_update().get(...) ran (security gate
            # follow-up, 2026-07-16 — the same TOCTOU window
            # VisitRecordPhotoCreateView already guards for VisitRecord).
            # Surface it as a normal 404 instead of a 500.
            raise Http404
