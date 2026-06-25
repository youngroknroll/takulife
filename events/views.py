from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from django.shortcuts import get_object_or_404

from .models import Event
from .queries import PUBLIC_LISTING_PAGE_SIZE, list_published_events, parse_public_listing_params
from .serializers import EventPosterUploadSerializer, EventSerializer
from .services import clear_event_poster, set_event_poster


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


class EventPosterView(APIView):
    """Staff-only endpoint to upload or delete an event's poster image.

    Authentication is explicitly restricted to SessionAuthentication to prevent
    BasicAuth from bypassing CSRF protection (the project has no global DRF
    DEFAULT_AUTHENTICATION_CLASSES setting, so DRF's default includes BasicAuth).
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        event = get_object_or_404(Event.objects.published(), pk=pk)
        serializer = EventPosterUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_event_poster(event=event, image=serializer.validated_data["image"])
        return Response({"poster_url": event.poster_image.url})

    def delete(self, request, pk):
        event = get_object_or_404(Event.objects.published(), pk=pk)
        clear_event_poster(event=event)
        return Response(status=204)
