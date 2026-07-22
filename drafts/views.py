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
    DraftStateError,
    DraftVocabError,
    create_draft_from_url,
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
            updated_draft = update_draft(draft_id=draft.id, updates=serializer.validated_data)
        except DraftStateError:
            return error_response("Only pending drafts can be updated.", 400)
        except DraftVocabError:
            return error_response(
                "category/region must be a known vocabulary slug.", 400
            )

        return Response(EventDraftSerializer(updated_draft).data, status=status.HTTP_200_OK)
