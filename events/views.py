from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from django.shortcuts import get_object_or_404

from core.analytics import record_event
from core.models import AnalyticsEvent

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
        # q present -> the user searched; absent -> a plain browse/filter
        # view. The two are mutually exclusive analytics events (PR-0e
        # checkpoint B10), recorded once per request.
        event_name = (
            AnalyticsEvent.EventName.EVENT_SEARCHED
            if params.get("q")
            else AnalyticsEvent.EventName.EVENT_LIST_VIEWED
        )
        record_event(event_name, user=self.request.user)
        return list_published_events(params)


class PublicEventDetailView(RetrieveAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.published()

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        record_event(
            AnalyticsEvent.EventName.EVENT_DETAIL_VIEWED,
            user=request.user,
            target_type="event",
            target_id=response.data["id"],
        )
        return response


class EventPosterView(APIView):
    """Staff-only endpoint to upload or delete an event's poster image.

    Authentication is explicitly restricted to SessionAuthentication to prevent
    BasicAuth from bypassing CSRF protection. The project's global DRF
    DEFAULT_AUTHENTICATION_CLASSES setting (config/settings.py) already pins
    this, but the local override stays as an explicit, view-level guard so
    this admin-only endpoint doesn't silently depend on the global setting.
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
