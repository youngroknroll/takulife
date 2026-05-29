from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import error_response, field_error_response

from .models import EventDraft
from .serializers import EventDraftSerializer, EventDraftUpdateSerializer
from .services import (
    DraftNotFoundError,
    DraftPublicationDuplicateError,
    DraftPublicationError,
    DraftStateError,
    approve_draft,
    reject_draft,
)


class AdminEventDraftListCreateView(ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = EventDraftSerializer
    queryset = EventDraft.objects.order_by("-id")


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
        if draft.review_status != EventDraft.ReviewStatus.PENDING:
            return error_response("Only pending drafts can be updated.", 400)
        return super().update(request, *args, **kwargs)


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
