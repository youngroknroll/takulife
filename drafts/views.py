from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import error_response, field_error_response

from .models import EventDraft
from .queries import draft_review_stats
from .serializers import EventDraftSerializer, EventDraftUpdateSerializer
from .services import (
    DraftCreationEmptyExtractionError,
    DraftCreationDuplicateError,
    DraftCreationFetchError,
    DraftCreationResponseTooLargeError,
    DraftCreationUnsupportedContentError,
    DraftCreationUnsafeUrlError,
    DraftNotFoundError,
    DraftPublicationDuplicateError,
    DraftPublicationMissingOfficialUrlError,
    DraftPublicationError,
    DraftStateError,
    approve_draft,
    create_draft_from_url,
    reject_draft,
    update_draft,
)


class AdminEventDraftStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(draft_review_stats())


class AdminEventDraftListCreateView(ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = EventDraftSerializer
    queryset = EventDraft.objects.order_by("-id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source_url = serializer.validated_data["source_url"]
        source_name = serializer.validated_data.get("source_name", "")

        try:
            draft = create_draft_from_url(source_url=source_url, source_name=source_name)
        except DraftCreationDuplicateError:
            return field_error_response(
                "source_url",
                "Event draft with this source URL already exists.",
            )
        except DraftCreationUnsafeUrlError:
            return error_response("Unsafe URL is not allowed.", 400)
        except DraftCreationUnsupportedContentError:
            return error_response("Only HTML content is supported.", 400)
        except DraftCreationResponseTooLargeError:
            return error_response("Fetched content is too large.", 400)
        except DraftCreationEmptyExtractionError:
            return error_response("Could not extract meaningful event content.", 400)
        except DraftCreationFetchError:
            return error_response("Failed to fetch source URL.", 503)

        response_data = EventDraftSerializer(draft).data
        headers = self.get_success_headers(response_data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)


class AdminEventDraftDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = EventDraftSerializer
    queryset = EventDraft.objects.all()
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return EventDraftUpdateSerializer
        return EventDraftSerializer

    def update(self, request, *args, **kwargs):
        draft = self.get_object()
        serializer = self.get_serializer(draft, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            updated_draft = update_draft(draft.id, serializer.validated_data)
        except DraftStateError:
            return error_response("Only pending drafts can be updated.", 400)

        return Response(EventDraftSerializer(updated_draft).data, status=status.HTTP_200_OK)


class AdminEventDraftApproveView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            result = approve_draft(pk)
        except DraftNotFoundError:
            return error_response("Not found.", 404)
        except DraftStateError:
            return error_response("Only pending drafts can be approved.", 400)
        except DraftPublicationDuplicateError:
            return field_error_response("official_url", "Event with this official URL already exists.")
        except DraftPublicationMissingOfficialUrlError:
            return field_error_response("official_url", "Official URL is required for publication.")
        except DraftPublicationError:
            return error_response("Event publication failed.", 503)

        data = EventDraftSerializer(result.draft).data
        data["event_id"] = result.event_id
        return Response(data, status=status.HTTP_200_OK)


class AdminEventDraftRejectView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            draft = reject_draft(pk)
        except DraftNotFoundError:
            return error_response("Not found.", 404)
        except DraftStateError:
            return error_response("Only pending drafts can be rejected.", 400)

        return Response(EventDraftSerializer(draft).data, status=status.HTTP_200_OK)
