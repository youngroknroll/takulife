from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination

from .models import Event
from .queries import PUBLIC_LISTING_PAGE_SIZE, list_published_events, parse_public_listing_params
from .serializers import EventSerializer


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
